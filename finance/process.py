from copy import deepcopy
from dataclasses import dataclass, InitVar, field
from easydict import EasyDict
from functools import reduce, partial, wraps
from icecream import ic
import argparse
import datetime,pytz
import dill
import glob
import json
import logging
import natsort
import numpy as np
import os
import pathlib
import sys
import time
logging.basicConfig(level=getattr(logging, os.environ.get('LOG_LEVEL','INFO').upper()))
import re
import copy
from transformers import AutoTokenizer, AutoModel
import threading

def build_parser():
    parser = argparse.ArgumentParser(description='Finance')
    parser.add_argument('--input_csv', type=str, help='input file')
    parser.add_argument('--input_timeout', type=int, help='input timeout',default=2)
    return parser

def main(args=None):
    args = isinstance(args, argparse.Namespace) or build_parser().parse_args(args)
    tokenizer = AutoTokenizer.from_pretrained("THUDM/chatglm3-6b", trust_remote_code=True)
    model = AutoModel.from_pretrained("THUDM/chatglm3-6b", trust_remote_code=True, device='cuda')
    model = model.eval()
    data_lines = [line.strip().split(',')[-1] for line in open(args.input_csv,encoding='utf-8').readlines()]

    profiling_start_time = time.time()
    loop_count = 1
    while loop_count:
        loop_count -= 1
        orig_chat_input_lines = open('finance/prompt.txt',encoding='utf-8').read()
        next_instance = True
        data_line_index = -1
        f = open('finance/process.log','w' ,encoding='utf-8')
        while next_instance and data_line_index < len(data_lines) - 1:
            # f.write(f"Processing line {line_index}\n")
            data_line_index += 1
            print (f"Processing line {data_line_index}")
            data = data_lines[data_line_index]
            history = []
            chat_input_lines = copy.deepcopy(orig_chat_input_lines).replace('<input>',data)
            chat_input_lines = chat_input_lines.split('<sep>')
            responses = []

            for chat_input_line in chat_input_lines:
                parsed_response, history = model.chat(tokenizer, chat_input_line, history=history)
                # f.write(response)
                print(parsed_response)
                responses.append(parsed_response)
            parsed_response_d = {}

            for key,parsed_response in zip(chat_input_lines[1:],responses[1:]):

                # f.write(f"{key}：{response}\n")
                key = key.split('，')[0].split('。')[0].strip("\n")

                parsed_response = parsed_response.strip("。")
                regex_match = re.fullmatch(r".+：(.+)",parsed_response)
                if regex_match is not None:
                    parsed_response = regex_match.group(1)

                if parsed_response.startswith("无明确") or parsed_response.startswith("未提及"):
                    parsed_response = "无"
                
                if key == "是否有抵押物":
                    if "有抵押物" in parsed_response and "无抵押物" not in parsed_response:
                        parsed_response = "是"
                    elif "无抵押物" in parsed_response and "有抵押物" not in parsed_response:
                        parsed_response = "否"
                    else:
                        parsed_response = "error"
                elif key == "逾期罚息":
                    regex_match = re.match(r'\d+(\.\d+)?%',parsed_response)
                    if regex_match is not None:
                        parsed_response = regex_match.group()
                    else:
                        parsed_response = "error"
                elif key == "借款利率方式":
                    if "月利率" in parsed_response and "年利率" not in parsed_response:
                        parsed_response = "月利率"
                    elif "年利率" in parsed_response and "月利率" not in parsed_response:
                        parsed_response = "年利率"
                    else:
                        parsed_response = "error"
                elif key == "借款金额":
                    # ends with 万元 or 元
                    # extract the float
                    regex_match = re.fullmatch(r'(\d+(\.\d+)?)万元',parsed_response)
                    if regex_match is not None:
                        parsed_response = str(int(regex_match.group(1)) * (10000 if "万元" in parsed_response else 1))
                    else:
                        parsed_response = "error"
                elif key == "原告名称":
                    regex_match = re.match(r'^[\u4e00-\u9fa5]{2,3},',parsed_response)
                    if regex_match is not None:
                        parsed_response = regex_match.group(0)
                    else:
                        pass
                elif key == "被告名称":
                    regex_match_0 = re.match(r'^([\u4e00-\u9fa5]{2,3}),',parsed_response)
                    regex_match_1 = re.match(r'^(.+),',parsed_response)
                    none_states = [regex_match_0 is None,regex_match_1 is None]
                    if none_states == [False,False]:
                        pass
                    elif none_states == [True,False]:
                        parsed_response = regex_match_0.group(0)
                    elif none_states == [False,True]:
                        parsed_response = regex_match_1.group(0)
                    else:
                        parsed_response = "error"
                else:
                    parsed_response_d[key] = parsed_response

            for k in ["被告所在地","原告所在地"]:
                if parsed_response_d["法院所在地"].endswith(parsed_response_d[k]):
                    parsed_response_d[k] = parsed_response_d["法院所在地"]
            ic(parsed_response_d)
            # logging.debug(parsed_responses)
            
                
            next_instance = input_with_timeout("Next instance? [y]/n): ",2) in ["y",None,"Y"]
        f.close()
        # next_round = input("Continue? [y]/n): ").lower() in ["y", ""]
    print('profiling cost time: %s' % (time.time() - profiling_start_time))

# Function to run input in a separate thread
def input_with_timeout(prompt, timeout):
    if abs(timeout) < 0.001:
        return ""

    def input_thread(result_list):
        result_list.append(input(prompt))

    result = []
    thread = threading.Thread(target=input_thread, args=(result,))
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        print("\nTimeout occurred - input not provided within the time limit.")
        return "y"  # or a default value
    else:
        return result[0]

if __name__ == '__main__':
    main()
