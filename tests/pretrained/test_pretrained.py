# -*- coding: utf-8 -*-
import pytest
import os
import pandas
import torch
import flair

from eznlp.token import TokenSequence
from eznlp.pretrained import ELMoConfig, BertLikeConfig, FlairConfig
from eznlp.pretrained.bert_like import truncate_for_bert_like, _tokenized2nested
from eznlp.training.utils import count_params
from eznlp.io import TabularIO


class TestFlairEmbedder(object):
    @pytest.mark.parametrize("agg_mode", ['last', 'mean'])
    def test_flair_embeddings(self, agg_mode, flair_lm):
        batch_tokenized_text = [["I", "like", "it", "."], 
                                ["Do", "you", "love", "me", "?"], 
                                ["Sure", "!"], 
                                ["Future", "it", "out"]]
        
        flair_emb = flair.embeddings.FlairEmbeddings(flair_lm)
        flair_sentences = [flair.data.Sentence(" ".join(sent), use_tokenizer=False) for sent in batch_tokenized_text]
        flair_emb.embed(flair_sentences)
        expected = torch.nn.utils.rnn.pad_sequence([torch.stack([tok.embedding for tok in sent]) for sent in flair_sentences], 
                                                   batch_first=True, 
                                                   padding_value=0.0)
        
        flair_config = FlairConfig(flair_lm=flair_lm, agg_mode=agg_mode)
        flair_embedder = flair_config.instantiate()
        
        
        batch_tokens = [TokenSequence.from_tokenized_text(tokenized_text) for tokenized_text in batch_tokenized_text]
        batch_flair_ins = flair_config.batchify([flair_config.exemplify(tokens) for tokens in batch_tokens])
        if agg_mode.lower() == 'last':
            assert (flair_embedder(**batch_flair_ins) == expected).all().item()
        else:
            assert (flair_embedder(**batch_flair_ins) != expected).any().item()
        
        
    @pytest.mark.parametrize("freeze", [True, False])
    @pytest.mark.parametrize("use_gamma", [True, False])
    def test_trainble_config(self, freeze, use_gamma, flair_lm):
        flair_config = FlairConfig(flair_lm=flair_lm, freeze=freeze, use_gamma=use_gamma)
        flair_embedder = flair_config.instantiate()
        
        expected_num_trainable_params = 0
        if not freeze:
            expected_num_trainable_params += count_params(flair_lm, return_trainable=False)
        if use_gamma:
            expected_num_trainable_params += 1
        assert count_params(flair_embedder) == expected_num_trainable_params
        
        
    def test_serialization(self, flair_fw_lm):
        config = FlairConfig(flair_lm=flair_fw_lm)
        
        config_path = "cache/flair_embedder.config"
        torch.save(config, config_path)
        assert os.path.getsize(config_path) < 1024 * 1024  # 1MB
        
        
class TestELMoEmbbeder(object):
    @pytest.mark.parametrize("mix_layers", ['trainable', 'top', 'average'])
    @pytest.mark.parametrize("use_gamma", [True, False])
    @pytest.mark.parametrize("freeze", [True, False])
    def test_trainble_config(self, mix_layers, use_gamma, freeze, elmo):
        elmo_config = ELMoConfig(elmo=elmo, freeze=freeze, mix_layers=mix_layers, use_gamma=use_gamma)
        elmo_embedder = elmo_config.instantiate()
        
        expected_num_trainable_params = 0
        if not freeze:
            expected_num_trainable_params += count_params(elmo, return_trainable=False) - 4
        if mix_layers.lower() == 'trainable':
            expected_num_trainable_params += 3
        if use_gamma:
            expected_num_trainable_params += 1
        
        assert count_params(elmo_embedder) == expected_num_trainable_params
        
        
    def test_serialization(self, elmo):
        config = ELMoConfig(elmo=elmo)
        
        config_path = "cache/elmo_embedder.config"
        torch.save(config, config_path)
        assert os.path.getsize(config_path) < 1024 * 1024  # 1MB
        
        
        
class TestBertLikeEmbedder(object):
    @pytest.mark.parametrize("mix_layers", ['trainable', 'top'])
    @pytest.mark.parametrize("use_gamma", [True])
    @pytest.mark.parametrize("freeze", [True])
    def test_trainble_config(self, mix_layers, use_gamma, freeze, bert_like_with_tokenizer):
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
        
        
    def test_serialization(self, bert_with_tokenizer):
        bert, tokenizer = bert_with_tokenizer
        config = BertLikeConfig(tokenizer=tokenizer, bert_like=bert)
        
        config_path = "cache/bert_embedder.config"
        torch.save(config, config_path)
        assert os.path.getsize(config_path) < 1024 * 1024  # 1MB



@pytest.mark.slow
@pytest.mark.parametrize("mode", ["head+tail", "head-only", "tail-only"])
def test_truncate_for_bert_like(self, mode, bert_with_tokenizer):
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
        
        