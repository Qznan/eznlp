# -*- coding: utf-8 -*-
import pytest
import os
import pandas
import torch

from eznlp.model import BertLikeConfig
from eznlp.model.bert_like import truncate_for_bert_like, _tokenized2nested
from eznlp.training.utils import count_params
from eznlp.io import TabularIO



@pytest.mark.parametrize("mix_layers", ['trainable', 'top'])
@pytest.mark.parametrize("use_gamma", [True])
@pytest.mark.parametrize("freeze", [True])
def test_trainble_config(mix_layers, use_gamma, freeze, bert_like_with_tokenizer):
    bert_like, tokenizer = bert_like_with_tokenizer
    bert_like_config = BertLikeConfig(bert_like=bert_like, tokenizer=tokenizer, 
                                      freeze=freeze, mix_layers=mix_layers, use_gamma=use_gamma)
    bert_like_embedder = bert_like_config.instantiate()
    
    expected_num_trainable_params = 0
    if not freeze:
        expected_num_trainable_params += count_params(bert_like, return_trainable=False)
    if mix_layers.lower() == 'trainable':
        expected_num_trainable_params += 13
    if use_gamma:
        expected_num_trainable_params += 1
    
    assert count_params(bert_like_embedder) == expected_num_trainable_params



def test_serialization(bert_with_tokenizer):
    bert, tokenizer = bert_with_tokenizer
    config = BertLikeConfig(tokenizer=tokenizer, bert_like=bert)
    
    config_path = "cache/bert_embedder.config"
    torch.save(config, config_path)
    assert os.path.getsize(config_path) < 1024 * 1024  # 1MB



@pytest.mark.slow
@pytest.mark.parametrize("mode", ["head+tail", "head-only", "tail-only"])
def test_truncate_for_bert_like(mode, bert_with_tokenizer):
    bert, tokenizer = bert_with_tokenizer
    max_len = tokenizer.model_max_length - 2
    
    tabular_io = TabularIO(text_col_id=3, label_col_id=2, sep="\t\t", mapping={"<sssss>": "\n"}, encoding='utf-8', case_mode='lower')
    data = tabular_io.read("data/Tang2015/yelp-2013-seg-20-20.test.ss")
    data = [data_entry for data_entry in data if len(data_entry['tokens']) >= max_len-10]
    assert max(len(data_entry['tokens']) for data_entry in data) > max_len
    
    data = truncate_for_bert_like(data, tokenizer, mode)
    sub_lens = [sum(len(word) for word in _tokenized2nested(data_entry['tokens'].raw_text, tokenizer)) for data_entry in data]
    sub_lens = pandas.Series(sub_lens)
    
    assert (sub_lens <= max_len).all()
    assert (sub_lens == max_len).sum() >= (len(sub_lens) / 2)
        
        