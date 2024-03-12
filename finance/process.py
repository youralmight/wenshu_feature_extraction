from rich.console import Console
console = Console()
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
    # preparing
    args = isinstance(args, argparse.Namespace) or build_parser().parse_args(args)
    tokenizer = AutoTokenizer.from_pretrained("THUDM/chatglm3-6b", trust_remote_code=True)
    model = AutoModel.from_pretrained("THUDM/chatglm3-6b", trust_remote_code=True, device='cuda')
    model = model.eval()
    data_lines = [line.strip().split(',')[-1] for line in open(args.input_csv,encoding='utf-8').readlines()]

    profiling_start_time = time.time()
    # preparing for loop
    data_line_index = -1
    next_instance = True
    while True:
        ic (next_instance)
        ic (data_line_index)
        ic (len(data_lines))
        if not (next_instance and data_line_index < len(data_lines) - 1):
            break
        with open ('finance/prompt.txt', 'r', encoding='utf-8') as fin:
            orig_chat_input_lines = fin.read()
        data_line_index += 1
        
        print (f"Processing line {data_line_index}")
        data = data_lines[data_line_index]
        history = []
        chat_input_lines = copy.deepcopy(orig_chat_input_lines).replace('<input>',data)
        chat_input_lines = chat_input_lines.split('<sep>')
        responses = []

        for chat_input_line in chat_input_lines:
            response, history = model.chat(tokenizer, chat_input_line, history=history)
            # print(response)
            responses.append(response)

        parsed_response_d = {}
        for key, response in zip(chat_input_lines[1:],responses[1:]):
            console.print(f"{response}",end=None)
            key = key.split('，')[0].split('。')[0].strip("\n")
            parsed_response = response.strip("。")
            regex_match = re.fullmatch(r".+：(.+)",parsed_response)
            if regex_match is not None:
                parsed_response = regex_match.group(1)

            if parsed_response.startswith("无明确") or parsed_response.startswith("未提及"):
                parsed_response = "未提及"
            elif key == "是否有抵押物":
                if "有抵押物" in parsed_response and "无抵押物" not in parsed_response:
                    parsed_response = "是"
                elif "无抵押物" in parsed_response and "有抵押物" not in parsed_response:
                    parsed_response = "否"
                elif parsed_response == "有":
                    parsed_response = "是"
                elif parsed_response == "无":
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
                parsed_response=parsed_response.replace(",","")
                regex_match = re.fullmatch(r'(\d+(\.\d+)?)万?元',parsed_response)
                if regex_match is not None:
                    parsed_response = str(float(regex_match.group(1)) * (10000 if "万元" in parsed_response else 1))
                else:
                    parsed_response = "error"
            elif key =='借款期限':
                parsed_response=parsed_response.replace("期","")
                regex_match = re.fullmatch(r'(\d+)个?月年(\d+)个?月',parsed_response)
                if regex_match is not None:
                    parsed_response = int(regex_match.group(1))*12 + int(regex_match.group(2))
                else:
                    parsed_response = "error"

            elif key in ["被告名称","原告名称"]:
                parsed_response = parsed_response.split('、')[0].split('。')[0]
                regex_match_0 = re.match(r'^([\u4e00-\u9fa5]+)',parsed_response)
                # regex_match_1 = re.match(r'^(.+),',parsed_response)
                regex_match_1 = None
                none_states = [regex_match_0 is not None,regex_match_1 is not None]
                if none_states == [False,False]:
                    pass
                elif none_states == [True,False]:
                    parsed_response = regex_match_0.group(0)
                elif none_states == [False,True]:
                    parsed_response = regex_match_1.group(0)
                else:
                    parsed_response = "error"
            else:
                parsed_response
            parsed_response_d[key] = parsed_response
            # print(f"\n")
            console.print(f"{key}: {parsed_response}\n",style="green")
            # f.flush()

        for k in ["被告所在地","原告所在地"]:
            if parsed_response_d["法院所在地"].endswith(parsed_response_d[k]):
                parsed_response_d[k] = parsed_response_d["法院所在地"]

        next_instance = input_with_timeout("Next instance? [y]/n): ",args.input_timeout) in ["y","",None,"Y"]
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
