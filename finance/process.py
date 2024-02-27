import copy
from transformers import AutoTokenizer, AutoModel
tokenizer = AutoTokenizer.from_pretrained("THUDM/chatglm3-6b", trust_remote_code=True)
model = AutoModel.from_pretrained("THUDM/chatglm3-6b", trust_remote_code=True, device='cuda')
model = model.eval()
orig_chat_input_lines = open('prompt.txt',encoding='utf-8').read()
lines = [l.strip().split(',')[-1] for l in open('wenshu2/2017年裁判文书数据_马克数据网/2017年01月裁判文书数据_民间_01月.csv',encoding='utf-8').readlines()[1:]]
for data in lines[:100]:
    history = []
    chat_input_lines = copy.deepcopy(orig_chat_input_lines).replace('<input>',data)
    chat_input_lines = chat_input_lines.split('<sep>')
    for chat_input_line in chat_input_lines:
        response, history = model.chat(tokenizer, chat_input_line, history=history)
        print(response)