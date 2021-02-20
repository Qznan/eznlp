# -*- coding: utf-8 -*-
import pytest
import torch
import allennlp.modules
import transformers
import flair

from eznlp import auto_device
from eznlp.pretrained import GloVe
from eznlp.sequence_tagging.io import ConllIO
from eznlp.text_classification.io import TabularIO


def pytest_addoption(parser):
    parser.addoption('--device', type=str, default='auto', help="device to run tests (`auto`, `cpu` or `cuda:x`)")
    
@pytest.fixture
def device(request):
    device_str = request.config.getoption('--device')
    if device_str == 'auto':
        return auto_device()
    else:
        return torch.device(device_str)
    
    
@pytest.fixture
def conll2003_demo():
    return ConllIO(text_col_id=0, tag_col_id=3, scheme='BIO1').read("data/conll2003/demo.eng.train")

@pytest.fixture
def yelp2013_demo():
    return TabularIO(text_col_id=3, label_col_id=2).read("data/Tang2015/demo.yelp-2013-seg-20-20.train.ss", 
                                                         encoding='utf-8', 
                                                         sep="\t\t", 
                                                         sentence_sep="<sssss>")


@pytest.fixture
def glove100():
    return GloVe("assets/vectors/glove.6B.100d.txt", encoding='utf-8')


@pytest.fixture
def elmo():
    return allennlp.modules.Elmo(options_file="assets/allennlp/elmo_2x1024_128_2048cnn_1xhighway_options.json", 
                                 weight_file="assets/allennlp/elmo_2x1024_128_2048cnn_1xhighway_weights.hdf5", 
                                 num_output_representations=1)


bert_path = "assets/transformers/bert-base-cased"
roberta_path = "assets/transformers/roberta-base"

@pytest.fixture
def bert_with_tokenizer():
    return (transformers.BertModel.from_pretrained(bert_path), 
            transformers.BertTokenizer.from_pretrained(bert_path))

@pytest.fixture
def bert4mlm_with_tokenizer():
    return (transformers.BertForMaskedLM.from_pretrained(bert_path), 
            transformers.BertTokenizer.from_pretrained(bert_path))

@pytest.fixture
def roberta_with_tokenizer():
    return (transformers.RobertaModel.from_pretrained(roberta_path), 
            transformers.RobertaTokenizer.from_pretrained(roberta_path))

@pytest.fixture
def roberta4mlm_with_tokenizer():
    return (transformers.RobertaForMaskedLM.from_pretrained(roberta_path), 
            transformers.RobertaTokenizer.from_pretrained(roberta_path))

@pytest.fixture(params=['bert', 'roberta'])
def bert_like_with_tokenizer(request, bert_with_tokenizer, roberta_with_tokenizer):
    if request.param == 'bert':
        return bert_with_tokenizer
    elif request.param == 'roberta':
        return roberta_with_tokenizer

@pytest.fixture(params=['bert', 'roberta'])
def bert_like4mlm_with_tokenizer(request, bert4mlm_with_tokenizer, roberta4mlm_with_tokenizer):
    if request.param == 'bert':
        return bert4mlm_with_tokenizer
    elif request.param == 'roberta':
        return roberta4mlm_with_tokenizer


@pytest.fixture
def flair_fw_lm():
    return flair.models.LanguageModel.load_language_model("assets/flair/lm-mix-english-forward-v0.2rc.pt")

@pytest.fixture
def flair_bw_lm():
    return flair.models.LanguageModel.load_language_model("assets/flair/lm-mix-english-backward-v0.2rc.pt")

@pytest.fixture(params=['fw', 'bw'])
def flair_lm(request, flair_fw_lm, flair_bw_lm):
    if request.param == 'fw':
        return flair_fw_lm
    elif request.param == 'bw':
        return flair_bw_lm
    