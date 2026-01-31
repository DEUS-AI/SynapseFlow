"""Training Data Formatter.

Formats extracted RLHF data for various training frameworks.

Supported formats:
- DPO (Direct Preference Optimization)
- SFT (Supervised Fine-Tuning)
- Alpaca (Instruction tuning)
- ShareGPT (Conversation format)
- HuggingFace Datasets
"""

from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


class OutputFormat(str, Enum):
    """Supported output formats."""
    DPO = "dpo"
    SFT = "sft"
    ALPACA = "alpaca"
    SHAREGPT = "sharegpt"
    OPENAI = "openai"
    JSONL = "jsonl"
    CSV = "csv"


@dataclass
class FormatterConfig:
    """Configuration for data formatting."""
    include_metadata: bool = False
    include_system_prompt: bool = True
    system_prompt: str = "You are a helpful medical knowledge assistant."
    max_length: Optional[int] = None
    split_ratio: tuple = (0.9, 0.05, 0.05)  # train, val, test


class TrainingDataFormatter:
    """
    Formats training data for various ML frameworks.

    Supports multiple output formats for different training approaches.
    """

    def __init__(self, config: Optional[FormatterConfig] = None):
        """
        Initialize formatter.

        Args:
            config: Optional formatter configuration
        """
        self.config = config or FormatterConfig()

    def format_dpo(
        self,
        preference_pairs: List[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        """
        Format for Direct Preference Optimization (DPO).

        Output format:
        {
            "prompt": "...",
            "chosen": "...",
            "rejected": "..."
        }
        """
        formatted = []

        for pair in preference_pairs:
            entry = {
                "prompt": self._clean_text(pair.get("prompt", "")),
                "chosen": self._clean_text(pair.get("chosen", "")),
                "rejected": self._clean_text(pair.get("rejected", "")),
            }

            if self.config.include_metadata:
                entry["metadata"] = {
                    "rating_gap": pair.get("rating_gap"),
                    "source": pair.get("source"),
                    "layers": pair.get("layers_involved", []),
                }

            formatted.append(entry)

        return formatted

    def format_sft(
        self,
        examples: List[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        """
        Format for Supervised Fine-Tuning (SFT).

        Output format:
        {
            "prompt": "...",
            "completion": "..."
        }
        """
        formatted = []

        for example in examples:
            instruction = example.get("instruction", "")
            input_text = example.get("input", "")
            output = example.get("output", "")

            # Combine instruction and input
            if input_text:
                prompt = f"{instruction}\n\n{input_text}"
            else:
                prompt = instruction

            entry = {
                "prompt": self._clean_text(prompt),
                "completion": self._clean_text(output),
            }

            if self.config.include_metadata:
                entry["metadata"] = {
                    "rating": example.get("rating"),
                    "source": example.get("source"),
                }

            formatted.append(entry)

        return formatted

    def format_alpaca(
        self,
        examples: List[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        """
        Format for Alpaca-style instruction tuning.

        Output format:
        {
            "instruction": "...",
            "input": "...",
            "output": "..."
        }
        """
        formatted = []

        for example in examples:
            entry = {
                "instruction": self._clean_text(example.get("instruction", "")),
                "input": self._clean_text(example.get("input", "")),
                "output": self._clean_text(example.get("output", "")),
            }

            if self.config.include_metadata:
                entry["metadata"] = {
                    "rating": example.get("rating"),
                    "source": example.get("source"),
                }

            formatted.append(entry)

        return formatted

    def format_sharegpt(
        self,
        examples: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Format for ShareGPT conversation style.

        Output format:
        {
            "conversations": [
                {"from": "human", "value": "..."},
                {"from": "gpt", "value": "..."}
            ]
        }
        """
        formatted = []

        for example in examples:
            conversations = []

            # Add system prompt if configured
            if self.config.include_system_prompt:
                conversations.append({
                    "from": "system",
                    "value": self.config.system_prompt,
                })

            # Add user message
            user_msg = example.get("input") or example.get("instruction", "")
            conversations.append({
                "from": "human",
                "value": self._clean_text(user_msg),
            })

            # Add assistant response
            conversations.append({
                "from": "gpt",
                "value": self._clean_text(example.get("output", "")),
            })

            entry = {"conversations": conversations}

            if self.config.include_metadata:
                entry["metadata"] = {
                    "rating": example.get("rating"),
                    "source": example.get("source"),
                }

            formatted.append(entry)

        return formatted

    def format_openai(
        self,
        examples: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Format for OpenAI fine-tuning API.

        Output format:
        {
            "messages": [
                {"role": "system", "content": "..."},
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."}
            ]
        }
        """
        formatted = []

        for example in examples:
            messages = []

            # Add system prompt
            if self.config.include_system_prompt:
                messages.append({
                    "role": "system",
                    "content": self.config.system_prompt,
                })

            # Add user message
            user_msg = example.get("input") or example.get("instruction", "")
            messages.append({
                "role": "user",
                "content": self._clean_text(user_msg),
            })

            # Add assistant response
            messages.append({
                "role": "assistant",
                "content": self._clean_text(example.get("output", "")),
            })

            formatted.append({"messages": messages})

        return formatted

    def format_dpo_openai(
        self,
        preference_pairs: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Format preference pairs for OpenAI-style DPO.

        Output format:
        {
            "prompt": [{"role": "user", "content": "..."}],
            "chosen": [{"role": "assistant", "content": "..."}],
            "rejected": [{"role": "assistant", "content": "..."}]
        }
        """
        formatted = []

        for pair in preference_pairs:
            prompt_messages = []

            if self.config.include_system_prompt:
                prompt_messages.append({
                    "role": "system",
                    "content": self.config.system_prompt,
                })

            prompt_messages.append({
                "role": "user",
                "content": self._clean_text(pair.get("prompt", "")),
            })

            entry = {
                "prompt": prompt_messages,
                "chosen": [{"role": "assistant", "content": self._clean_text(pair.get("chosen", ""))}],
                "rejected": [{"role": "assistant", "content": self._clean_text(pair.get("rejected", ""))}],
            }

            formatted.append(entry)

        return formatted

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        if not text:
            return ""

        # Basic cleaning
        text = text.strip()

        # Truncate if configured
        if self.config.max_length and len(text) > self.config.max_length:
            text = text[:self.config.max_length] + "..."

        return text

    def split_dataset(
        self,
        data: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Split data into train/val/test sets.

        Returns:
            Dict with 'train', 'validation', 'test' keys
        """
        import random
        random.shuffle(data)

        n = len(data)
        train_ratio, val_ratio, _ = self.config.split_ratio

        train_end = int(n * train_ratio)
        val_end = int(n * (train_ratio + val_ratio))

        return {
            "train": data[:train_end],
            "validation": data[train_end:val_end],
            "test": data[val_end:],
        }


def export_to_file(
    data: List[Dict[str, Any]],
    output_path: Union[str, Path],
    format: OutputFormat = OutputFormat.JSONL,
) -> Path:
    """
    Export formatted data to a file.

    Args:
        data: List of formatted records
        output_path: Output file path
        format: Output format

    Returns:
        Path to created file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if format in (OutputFormat.JSONL, OutputFormat.DPO, OutputFormat.SFT,
                  OutputFormat.ALPACA, OutputFormat.SHAREGPT, OutputFormat.OPENAI):
        # JSONL format
        with open(output_path, 'w', encoding='utf-8') as f:
            for record in data:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')

    elif format == OutputFormat.CSV:
        import csv

        if not data:
            return output_path

        # Get all keys
        keys = set()
        for record in data:
            keys.update(record.keys())
        keys = sorted(keys)

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for record in data:
                # Flatten nested dicts for CSV
                flat_record = {}
                for k, v in record.items():
                    if isinstance(v, (dict, list)):
                        flat_record[k] = json.dumps(v)
                    else:
                        flat_record[k] = v
                writer.writerow(flat_record)

    logger.info(f"Exported {len(data)} records to {output_path}")
    return output_path


def export_to_huggingface(
    data: List[Dict[str, Any]],
    dataset_name: str,
    split_data: bool = True,
    push_to_hub: bool = False,
    hub_repo: Optional[str] = None,
) -> Any:
    """
    Export data as a HuggingFace Dataset.

    Args:
        data: List of formatted records
        dataset_name: Name for the dataset
        split_data: Whether to split into train/val/test
        push_to_hub: Whether to push to HuggingFace Hub
        hub_repo: Repository name on HuggingFace Hub

    Returns:
        HuggingFace Dataset or DatasetDict
    """
    try:
        from datasets import Dataset, DatasetDict
    except ImportError:
        logger.error("HuggingFace datasets not installed. Run: pip install datasets")
        raise ImportError("Please install datasets: pip install datasets")

    if split_data:
        formatter = TrainingDataFormatter()
        splits = formatter.split_dataset(data)

        dataset = DatasetDict({
            "train": Dataset.from_list(splits["train"]),
            "validation": Dataset.from_list(splits["validation"]),
            "test": Dataset.from_list(splits["test"]),
        })
    else:
        dataset = Dataset.from_list(data)

    if push_to_hub and hub_repo:
        dataset.push_to_hub(hub_repo)
        logger.info(f"Pushed dataset to HuggingFace Hub: {hub_repo}")

    return dataset


def format_for_training(
    preference_pairs: List[Dict[str, Any]],
    sft_examples: List[Dict[str, Any]],
    output_format: OutputFormat,
    config: Optional[FormatterConfig] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Convenience function to format all data for training.

    Args:
        preference_pairs: List of preference pairs
        sft_examples: List of SFT examples
        output_format: Desired output format
        config: Optional formatter configuration

    Returns:
        Dict with 'preference_pairs' and 'sft_examples' formatted data
    """
    formatter = TrainingDataFormatter(config)

    result = {
        "preference_pairs": [],
        "sft_examples": [],
    }

    if preference_pairs:
        if output_format == OutputFormat.DPO:
            result["preference_pairs"] = formatter.format_dpo(preference_pairs)
        elif output_format == OutputFormat.OPENAI:
            result["preference_pairs"] = formatter.format_dpo_openai(preference_pairs)
        else:
            result["preference_pairs"] = formatter.format_dpo(preference_pairs)

    if sft_examples:
        if output_format == OutputFormat.SFT:
            result["sft_examples"] = formatter.format_sft(sft_examples)
        elif output_format == OutputFormat.ALPACA:
            result["sft_examples"] = formatter.format_alpaca(sft_examples)
        elif output_format == OutputFormat.SHAREGPT:
            result["sft_examples"] = formatter.format_sharegpt(sft_examples)
        elif output_format == OutputFormat.OPENAI:
            result["sft_examples"] = formatter.format_openai(sft_examples)
        else:
            result["sft_examples"] = formatter.format_alpaca(sft_examples)

    return result
