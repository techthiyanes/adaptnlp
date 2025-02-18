# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/07_summarization.ipynb (unless otherwise specified).

__all__ = ['logger', 'TransformersSummarizer', 'EasySummarizer']

# Cell
import logging
from typing import List, Dict, Union
from collections import defaultdict

import torch
from torch.utils.data import TensorDataset, DataLoader

from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    PreTrainedTokenizer,
    PreTrainedModel,
    T5ForConditionalGeneration,
    BartForConditionalGeneration,
)

from ..callback import GeneratorCallback
from ..model import AdaptiveModel
from ..model_hub import HFModelResult, FlairModelResult

from fastcore.basics import store_attr
from fastcore.meta import delegates

from fastai.callback.core import Callback, CancelBatchException
from fastai.torch_core import apply

# Cell
logger = logging.getLogger(__name__)

# Cell
class TransformersSummarizer(AdaptiveModel):
    "Adaptive model for Transformer's Conditional Generation or Language Models (Transformer's T5 and Bart conditiional generation models have a language modeling head)"
    def __init__(
        self,
        tokenizer: PreTrainedTokenizer, # A tokenizer object from Huggingface's transformers (TODO)and tokenizers
        model: PreTrainedModel # A transformers Conditional Generation (Bart or T5) or Language model
    ):
        # Load up tokenizer
        self.tokenizer = tokenizer

        super().__init__()
        # Sets internal model
        super().set_model(model)

        # Set inputs to come in as `dict`
        super().set_as_dict(True)

    @classmethod
    def load(
        cls,
        model_name_or_path: str # A key string of one of Transformer's pre-trained Summarizer Model
    ) -> AdaptiveModel:
        "Class method for loading and constructing this classifier"
        tokenizer = AutoTokenizer.from_pretrained(model_name_or_path)
        model = AutoModelForSeq2SeqLM.from_pretrained(model_name_or_path)
        summarizer = cls(tokenizer, model)
        return summarizer

    def predict(
        self,
        text: Union[List[str], str], # Sentences to run inference on
        mini_batch_size: int = 32, # Mini batch size
        num_beams: int = 4, # Number of beams for beam search. Must be between 1 and infinity. 1 means no beam search.
        min_length: int = 0, # The min length of the sequence to be generated
        max_length: int = 128, # The max length of the sequence to be generated. Between min_length and infinity
        early_stopping: bool = True, # If set to True beam search is stopped when at least num_beams sentences finished per batch
        **kwargs, # Optional arguments for the Transformers `PreTrainedModel.generate()` method
    ) -> List[str]: # A list of predicted summarizations
        "Predict method for running inference using the pre-trained sequence classifier model"

        # Make all inputs list
        if isinstance(text, str):
            text = [text]

        # T5 requires 'summarize: ' precursor text for pre-trained summarizer
        if isinstance(self.model, T5ForConditionalGeneration):
            text = [f'summarize: {t}' for t in text]

        dataset = self._tokenize(text)
        dl = DataLoader(dataset, batch_size=mini_batch_size)

        summaries = []

        logger.info(f'Running summarizer on {len(dataset)} text sequences')
        logger.info(f'Batch size = {mini_batch_size}')

        cb = GeneratorCallback(num_beams, min_length, max_length, early_stopping, **kwargs)

        preds,_ = super().get_preds(dl=dl, cbs=[cb])

        preds = apply(lambda x: x.squeeze(0), preds)

        for o in preds:
            summaries.append(
                [
                    self.tokenizer.decode(
                        o,
                        skip_special_tokens=True,
                        clean_up_tokenization_spaces=False,
                    )
                ].pop()
            )

        return {'summaries':summaries}

    def _tokenize(self, text: Union[List[str], str]) -> TensorDataset:
        "Batch tokenizes text and produces a `TensorDataset` with text"

        # Pre-trained Bart summarization model has a max length fo 1024 tokens for input
        if isinstance(self.model, BartForConditionalGeneration):
            tokenized_text = self.tokenizer.batch_encode_plus(
                text,
                return_tensors="pt",
                max_length=1024,
                add_special_tokens=True,
                padding="max_length",
            )
        else:
            tokenized_text = self.tokenizer.batch_encode_plus(
                text,
                return_tensors="pt",
                padding="max_length",
                add_special_tokens=True,
            )

        # Bart doesn't use `token_type_ids`
        dataset = TensorDataset(
            tokenized_text["input_ids"],
            tokenized_text["attention_mask"],
        )

        return dataset

# Cell
class EasySummarizer:
    "Summarization Module"
    def __init__(self):
        self.summarizers: Dict[AdaptiveModel] = defaultdict(bool)

    def summarize(
        self,
        text: Union[List[str], str], # Sentences to run inference on
        model_name_or_path: Union[str, HFModelResult] = "t5-small", # A model id or path to a pre-trained model repository or custom trained model directory
        mini_batch_size: int = 32, # Mini batch size
        num_beams: int = 4, # Number of beams for beam search. Must be between 1 and infinity. 1 means no beam search
        min_length: int = 0, # The max length of the sequence to be generated. Between min_length and infinity
        max_length: int = 128, # The max length of the sequence to be generated. Between min_length and infinity
        early_stopping: bool = True, # If set to True beam search is stopped when at least num_beams sentences finished per batch
        **kwargs, # Optional arguments for the Transformers `PreTrainedModel.generate()` method
    ) -> List[str]: # A list of predicted summaries
        "Predict method for running inference using the pre-trained sequence classifier model"
        name = getattr(model_name_or_path, 'name', model_name_or_path)
        if not self.summarizers[name]:
            self.summarizers[name] = TransformersSummarizer.load(
                name
            )

        summarizer = self.summarizers[name]
        return summarizer.predict(
            text=text,
            mini_batch_size=mini_batch_size,
            num_beams=num_beams,
            min_length=min_length,
            max_length=max_length,
            early_stopping=early_stopping,
            **kwargs,
        )