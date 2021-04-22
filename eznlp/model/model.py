# -*- coding: utf-8 -*-
from typing import List
import torch

from ..token import TokenSequence
from ..data.wrapper import Batch
from ..config import Config, ConfigDict
from .embedder import OneHotConfig
from .encoder import EncoderConfig
from .nested_embedder import SoftLexiconConfig


class ModelConfig(Config):
    """Configurations of a model. 
    
    model
      ├─decoder(*)
      └─intermediate2
          ├─intermediate1
          │   ├─ohots
          │   ├─mhots
          │   └─nested_ohots
          ├─elmo
          ├─bert_like
          ├─flair_fw
          └─flair_bw
    """
    
    _embedder_names = ['ohots', 'mhots', 'nested_ohots']
    _encoder_names = ['intermediate1', 'intermediate2']
    _pretrained_names = ['elmo', 'bert_like', 'flair_fw', 'flair_bw']
    _all_names = _embedder_names + ['intermediate1'] + _pretrained_names + ['intermediate2']
    
    def __init__(self, **kwargs):
        self.ohots = kwargs.pop('ohots', ConfigDict({'text': OneHotConfig(field='text')}))
        self.mhots = kwargs.pop('mhots', None)
        self.nested_ohots = kwargs.pop('nested_ohots', None)
        self.intermediate1 = kwargs.pop('intermediate1', None)
        
        self.elmo = kwargs.pop('elmo', None)
        self.bert_like = kwargs.pop('bert_like', None)
        self.flair_fw = kwargs.pop('flair_fw', None)
        self.flair_bw = kwargs.pop('flair_bw', None)
        self.intermediate2 = kwargs.pop('intermediate2', EncoderConfig(arch='LSTM'))
        super().__init__(**kwargs)
        
        
    @property
    def valid(self):
        return all(getattr(self, name) is None or getattr(self, name).valid for name in self._all_names)
        
    @property
    def name(self):
        return self._name_sep.join(getattr(self, name).name for name in self._all_names if getattr(self, name) is not None)
        
    def __repr__(self):
        return self._repr_config_attrs(self.__dict__)
    
    @property
    def full_emb_dim(self):
        return sum(getattr(self, name).out_dim for name in self._embedder_names if getattr(self, name) is not None)
        
    @property
    def full_hid_dim(self):
        if self.intermediate1 is not None:
            full_hid_dim = self.intermediate1.out_dim
        else:
            full_hid_dim = self.full_emb_dim
        full_hid_dim += sum(getattr(self, name).out_dim for name in self._pretrained_names if getattr(self, name) is not None)
        return full_hid_dim
        
    def build_vocabs_and_dims(self, *partitions):
        if self.ohots is not None:
            for c in self.ohots.values():
                c.build_vocab(*partitions)
                
        if self.mhots is not None:
            for c in self.mhots.values():
                c.build_dim(partitions[0][0]['tokens'])
                
        if self.nested_ohots is not None:
            for c in self.nested_ohots.values():
                c.build_vocab(*partitions)
                if isinstance(c, SoftLexiconConfig):
                    # Skip the last split (assumed to be test set)
                    c.build_freqs(*partitions[:-1])
                    
        if self.intermediate1 is not None:
            self.intermediate1.in_dim = self.full_emb_dim
            
        if self.intermediate2 is not None:
            self.intermediate2.in_dim = self.full_hid_dim
            
            
    def exemplify(self, tokens: TokenSequence):
        example = {}
        
        if self.ohots is not None:
            example['ohots'] = {f: c.exemplify(tokens) for f, c in self.ohots.items()}
        
        if self.mhots is not None:
            example['mhots'] = {f: c.exemplify(tokens) for f, c in self.mhots.items()}
            
        if self.nested_ohots is not None:
            example['nested_ohots'] = {f: c.exemplify(tokens) for f, c in self.nested_ohots.items()}
            
        for name in self._pretrained_names:
            if getattr(self, name) is not None:
                example[name] = getattr(self, name).exemplify(tokens)
                
        return example
        
    
    def batchify(self, batch_examples: List[dict]):
        batch = {}
        
        if self.ohots is not None:
            batch['ohots'] = {f: c.batchify([ex['ohots'][f] for ex in batch_examples]) for f, c in self.ohots.items()}
            
        if self.mhots is not None:
            batch['mhots'] = {f: c.batchify([ex['mhots'][f] for ex in batch_examples]) for f, c in self.mhots.items()}
        
        if self.nested_ohots is not None:
            batch['nested_ohots'] = {f: c.batchify([ex['nested_ohots'][f] for ex in batch_examples]) for f, c in self.nested_ohots.items()}
        
        for name in self._pretrained_names:
            if getattr(self, name) is not None:
                batch[name] = getattr(self, name).batchify([ex[name] for ex in batch_examples])
                
        return batch
        
    
    
class Model(torch.nn.Module):
    def __init__(self, config: ModelConfig):
        super().__init__()
        for name, c in config.__dict__.items():
            if c is not None:
                setattr(self, name, c.instantiate())
                
                
    def get_full_embedded(self, batch: Batch):
        embedded = []
        
        if hasattr(self, 'ohots'):
            ohots_embedded = [self.ohots[f](batch.ohots[f]) for f in self.ohots]
            embedded.extend(ohots_embedded)
            
        if hasattr(self, 'mhots'):
            mhots_embedded = [self.mhots[f](batch.mhots[f]) for f in self.mhots]
            embedded.extend(mhots_embedded)
            
        if hasattr(self, 'nested_ohots'):
            nested_ohots_embedded = [self.nested_ohots[f](**batch.nested_ohots[f], seq_lens=batch.seq_lens) for f in self.nested_ohots]
            embedded.extend(nested_ohots_embedded)
            
        return torch.cat(embedded, dim=-1)
    
    
    def get_full_hidden(self, batch: Batch):
        full_hidden = []
        
        if any([hasattr(self, name) for name in ModelConfig._embedder_names]):
            embedded = self.get_full_embedded(batch)
            if hasattr(self, 'intermediate1'):
                full_hidden.append(self.intermediate1(embedded, batch.mask))
            else:
                full_hidden.append(embedded)
                
        for name in ModelConfig._pretrained_names:
            if hasattr(self, name):
                full_hidden.append(getattr(self, name)(**getattr(batch, name)))
                
        full_hidden = torch.cat(full_hidden, dim=-1)
        
        if hasattr(self, 'intermediate2'):
            return self.intermediate2(full_hidden, batch.mask)
        else:
            return full_hidden
        
    def pretrained_parameters(self):
        params = []
        
        if hasattr(self, 'elmo'):
            params.extend(self.elmo.elmo._elmo_lstm.parameters())
        
        if hasattr(self, 'bert_like'):
            params.extend(self.bert_like.bert_like.parameters())
            
        if hasattr(self, 'flair_fw'):
            params.extend(self.flair_fw.flair_lm.parameters())
        if hasattr(self, 'flair_bw'):
            params.extend(self.flair_bw.flair_lm.parameters())
        
        return params
    
    