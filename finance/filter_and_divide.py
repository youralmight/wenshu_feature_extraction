import re
import glob
import tqdm
import pandas
from copy import deepcopy
from dataclasses import dataclass, InitVar, field
from easydict import EasyDict
from functools import reduce, partial, wraps
from icecream import ic
import argparse
import datetime,pytz
import dill
import json
import logging
import numpy as np
import os
import pathlib
import sys
import time
logging.basicConfig(level=getattr(logging, os.environ.get('LOG_LEVEL','INFO').upper()))

# results_tmp = {}
# results_tmp2 = {}

def build_filter_and_divide_parser():
    parser = argparse.ArgumentParser(description='Filter and divide')
    parser.add_argument('--input', type=str, help='input file')
    return parser
tags = ["银行借贷", "平台", "民间", "others", "non-finance"]
keys_to_write = ['民间','银行','平台']
def filter_and_divide(args):
    results = {}
    invalid_count = 0
    parse_fail_count = 0
    total_count = None
    last_ic_time = time.time()
    with open (args.input) as f:
        headers = f.readline().strip().split(',')
        for line_index, line in enumerate(f):
            total_count = line_index + 1 

            orginal_line = line

            def rep_func(match):
                matched_string = match.group(0)
                matched_string = "，".join(matched_string[1:-1].split(','))
                return matched_string
            line = re.sub(r'"(\s|\S)+?"',rep_func,line)
            line = line.replace('{edithtml:","content:}','')

            line = line.strip().split(',')
            fixed = None
            if len(line) == len(headers):
                fixed = True
            
            
            # elif len(line) == len(headers)+1:
            #     if line[11].startswith('"') and line[12].endswith('"'):
            #         tmp = f"{line[11]}，{line[12]}"
            #         del line[11]
            #         del line[11]
            #         line.insert(11,tmp)
            tags = []
            if fixed:
                line_dict = dict(zip(headers, line))
                try: 
                    assert len(line_dict) == len(headers), "len(line_dict) != len(headers)"
                    assert '全文' in line_dict, "全文 missing"
                    assert len(line_dict['全文']) > 0, "全文 missing"
                    assert len(line_dict['全文'])>100 , "全文 too short"
                    assert len(line_dict['案由'])>0, "anyou missing"
                    try:
                        int(line_dict['案件类型编码'])
                    except:
                        raise AssertionError(f"案件类型编码 {line_dict['案件类型编码']} is not int")
                except AssertionError as e:
                    # check message
                    if e.args[0] not in ["anyou missing"]:
                        invalid_count += 1
                        if(invalid_count<100):
                            if len(",".join(line))<1000: continue 
                            line[-1] = line[-1][:300]
                            line_dict = dict(zip(headers, line))
                            # print(headers)
                            ic(args.input)
                            print(line_dict)
                            print(line)
                    continue

                if ('利率' in line_dict['全文'] and '金融' in line_dict['案由']) and ('一审' in line_dict['审理程序']) and ('利率' in line_dict['全文']):
                    tags.append('银行借贷')
                if ('小额' in line_dict['案由'] or '小额' in line_dict['案由']) and ('一审' in line_dict['审理程序']) and ('利率' in line_dict['全文']):
                    tags.append('平台')
                if ('民间' in line_dict['案由'] or '民间借款' in line_dict['案由']) and ('一审' in line_dict['审理程序']) and ('利率' in line_dict['全文']):
                    tags.append('民间')

                if len(tags) == 0 and '利率' in line_dict['全文']:
                    tags.append('others')
                
                if not '利率' in line_dict['全文']:
                    tags.append('non-finance')
            else:
                # line = [x[:20] for x in line]
                parse_fail_count+=1
                # print(",".join(line))
            
            # print(tags)
            for tag_index,tag  in enumerate(tags):
                deal_date = line_dict['裁判日期']
                deal_month = deal_date.split('-')[1]
                result_key = f"{tag}_{deal_month}月"
                results[result_key] = results.get(result_key, [])
                results[result_key].append(line_dict)
            
            # # ic every 2 seconds
            # if time.time() - last_ic_time > 2:
            #     last_ic_time = time.time()
            #     ic(line_index)
            #     ic(parse_fail_count)
            #     for key, value in results.items():
            #         ic(key, len(value))
            

    last_ic_time = time.time()
    ic(total_count)
    ic(invalid_count)
    ic(parse_fail_count)
    for key, value in results.items():
        ic(key, len(value))
    for k in results.keys():
        if not any([t_k in k for t_k in keys_to_write]): continue
        output_file = f"{args.input.split('.')[0]}_{k}.csv"
        output_file_view = f"{args.input.split('.')[0]}_{k}_view.csv"
        f = open(output_file, 'w')
        f_view = open(output_file_view, 'w')
        for i, line_dict in enumerate(results[k]):
            if i<1000:
                f_view.write(','.join([ line_dict[header] for header in headers ]) + '\n')
            f.write(','.join([ line_dict[header] for header in headers ]) + '\n')
        f.close()
        f_view.close()

    return results

def batch_filter_and_divide(args):
    csv_files = glob.glob(args.input_dir + '/**/*.csv',recursive=True)
    csv_files = [ f for f in csv_files if not any([k in f for k in keys_to_write])]
    csv_files = sorted(csv_files, key=os.path.getsize, reverse=False)
    results={}
    total_file_size = sum([os.path.getsize(filepath) for filepath in csv_files])
    with tqdm.tqdm(total=total_file_size, file=sys.stdout) as pbar:
        for filepath in csv_files:
            d_arg = EasyDict({
                "input": filepath,
            })
            logging.info(f"Processing {filepath}")
            filter_and_divide(d_arg)
            results[filepath]=filter_and_divide(d_arg)
            pbar.update(os.path.getsize(filepath))
            # open('/tmp/wenshu2/results_tmp.json','w').write(json.dumps(results_tmp,ensure_ascii=False,indent=2))
            # open('/tmp/wenshu2/results_tmp2.json','w').write(json.dumps(results_tmp2,ensure_ascii=False,indent=2))

    # print(list(results_tmp))
    print()
    # print(list(results_tmp2))
    return results
        

if __name__ == '__main__':
    # pass
    result = batch_filter_and_divide(EasyDict({"input_dir": os.environ.get('INPUT_DIR',"/tmp/wenshu2")}))

# for key, value in results.items():
#     output_file = f"{args.output_dir}/{key}.csv"
#     with open(output_file, 'w') as f:
#         f.write(','.join(headers) + '\n')
#         for line in value:
#             f.write(','.join(line.values()) + '\n')

#     with open(f"{args.output_dir}/{key}_view.csv", 'w') as f:
#         f.write(','.join(headers) + '\n')
#         for line in value[:1000]:
#             f.write(','.join(line.values()) + '\n')

