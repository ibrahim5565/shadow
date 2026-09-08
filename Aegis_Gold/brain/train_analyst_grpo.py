import re
import json
import logging
from typing import Dict, Any, List

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AnalystGRPO")

# ---------------------------------------------------------------------------
# 1. Deterministic Reward Functions (Plain Python, No API Calls)
# ---------------------------------------------------------------------------

def parse_output(model_output: str) -> tuple[str, dict]:
    """Extracts thought and verdict JSON from raw model output using XML/markdown tags."""
    thought = ""
    verdict = {}
    
    # Parse thought
    thought_match = re.search(r"<thought>(.*?)</thought>", model_output, re.DOTALL | re.IGNORECASE)
    if thought_match:
        thought = thought_match.group(1).strip()
        
    # Parse verdict
    verdict_match = re.search(r"<verdict>(.*?)</verdict>", model_output, re.DOTALL | re.IGNORECASE)
    if verdict_match:
        verdict_str = verdict_match.group(1).strip()
        try:
            # Clean up potential markdown formatting block
            verdict_str = re.sub(r"```json\s*", "", verdict_str)
            verdict_str = re.sub(r"\s*```", "", verdict_str)
            verdict = json.loads(verdict_str)
        except Exception:
            # Try a fuzzy extract if JSON is slightly malformed
            try:
                # Look for matching brace block
                json_block = re.search(r"\{.*\}", verdict_str, re.DOTALL)
                if json_block:
                    verdict = json.loads(json_block.group(0))
            except Exception:
                pass
                
    return thought, verdict


def grounding_check(thought: str, prompt_data: dict) -> float:
    """Reward checking if the thought block quotes actual numbers/regimes from the prompt."""
    if not thought:
        return 0.0
        
    score = 0.0
    text = thought.lower()
    
    # Check if volatility regime name is mentioned
    regime = prompt_data.get("market_microstructure", {}).get("volatility_regime", "").lower()
    if regime and regime in text:
        score += 0.25
        
    # Check if current spread is mentioned
    spread = prompt_data.get("market_microstructure", {}).get("current_spread")
    if spread is not None and str(int(float(spread))) in text:
        score += 0.25
        
    # Check if win rate or profit factor is mentioned
    win_rate = prompt_data.get("performance_context", {}).get("reason_code_historical_win_rate")
    if win_rate is not None and f"{win_rate:.1f}" in text or f"{int(win_rate)}" in text:
        score += 0.25
        
    # Check if HTF bias is mentioned
    htf_bias = prompt_data.get("structure_context", {}).get("htf_bias", "").lower()
    if htf_bias and htf_bias in text:
        score += 0.25
        
    return score


def calibration_check(verdict: dict, perf_context: dict) -> float:
    """Reward checking if verdict.historical_edge aligns with performance context metrics."""
    if not verdict:
        return 0.0
        
    stated_edge = verdict.get("historical_edge", "neutral").lower()
    win_rate = perf_context.get("reason_code_historical_win_rate", 50.0)
    pf = perf_context.get("profit_factor", 1.0)
    
    # Determine correct edge programmatically
    if win_rate >= 55.0 and pf >= 1.5:
        ideal_edge = "positive"
    elif win_rate <= 45.0 or pf <= 1.0:
        ideal_edge = "negative"
    else:
        ideal_edge = "neutral"
        
    return 1.0 if stated_edge == ideal_edge else 0.0


def structure_check(verdict: dict, struct_context: dict) -> float:
    """Reward checking if verdict.structure_alignment matches SMC context."""
    if not verdict:
        return 0.0
        
    stated_align = verdict.get("structure_alignment", "neutral").lower()
    htf = struct_context.get("htf_bias", "").lower()
    trigger = struct_context.get("ltf_trigger", "").lower()
    
    # Simple rule: if HTF bias exists and trigger is present, structure aligns
    if htf in ("bullish", "bearish") and trigger in ("bos", "choch", "sweep"):
        ideal_align = "confirming"
    elif htf == "neutral" or not trigger:
        ideal_align = "neutral"
    else:
        ideal_align = "contradicting"
        
    return 1.0 if stated_align == ideal_align else 0.0


def outcome_check(verdict: dict, actual_outcome: str) -> float:
    """Reward checking if analyst recommendation aligns with the actual realized trade outcome."""
    if not verdict:
        return 0.0
        
    rec = verdict.get("recommendation", "").lower() # "approve" | "approve_reduced" | "reject"
    
    if actual_outcome == "WIN":
        if rec in ("approve", "approve_reduced"):
            return 1.0  # correct decision: let the winner run
        elif rec == "reject":
            return 0.25 # slightly sub-optimal: missed a winner, but safe
    elif actual_outcome == "LOSS":
        if rec == "reject":
            return 1.0  # correct decision: avoided a losing trade
        elif rec == "approve_reduced":
            return 0.1  # penalty reduction: went in with smaller size
        elif rec == "approve":
            return -1.0 # high penalty: approved a full-size losing trade
            
    return 0.0


def reward_fn(prompt_data: dict, model_output: str) -> float:
    """
    Combined deterministic reward function for GRPO training.
    Values sum up to a maximum of 1.0.
    """
    thought, verdict = parse_output(model_output)
    
    # If output structure is totally invalid (missing tags), return zero reward
    if not thought or not verdict:
        return 0.0
        
    g_score = grounding_check(thought, prompt_data)
    c_score = calibration_check(verdict, prompt_data.get("performance_context", {}))
    s_score = structure_check(verdict, prompt_data.get("structure_context", {}))
    o_score = outcome_check(verdict, prompt_data.get("actual_trade_outcome", "UNKNOWN"))
    
    # Combined weighted score
    score = (g_score * 0.25) + (c_score * 0.25) + (s_score * 0.25) + (o_score * 0.25)
    return float(score)


# ---------------------------------------------------------------------------
# 2. Open-Source GRPO Trainer using Unsloth and TRL
# ---------------------------------------------------------------------------

def run_grpo_training():
    """
    Sets up the GRPO training pipeline.
    Note: Requires GPU with CUDA and Unsloth / TRL installed.
    """
    try:
        from unsloth import FastLanguageModel
        from trl import GRPOTrainer, GRPOConfig
        import torch
        from datasets import load_dataset
    except ImportError:
        logger.warning(
            "⚠️ Unsloth/TRL/PyTorch dependencies missing. "
            "To run the GRPO loop, execute: pip install unsloth trl torch transformers"
        )
        return

    logger.info("Initializing Qwen2.5-1.5B-Instruct Model for GRPO...")
    
    # Max sequence length (up to 4096 supported by Qwen)
    max_seq_length = 4096
    
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="unsloth/Qwen2.5-1.5B-Instruct",
        max_seq_length=max_seq_length,
        load_in_4bit=True, # 4-bit quantization keeps VRAM low (runs on 8GB VRAM)
    )
    
    # Configure LoRA Adapter PEFT
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        lora_alpha=16,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=3407,
    )

    # 1. Load SFT SFT dataset we compiled in Task 3
    dataset_path = "data/analyst_sft_dataset.jsonl"
    if not os.path.exists(dataset_path):
        logger.error(f"Dataset path {dataset_path} not found. Please run train_analyst_dataset.py first.")
        return
        
    dataset = load_dataset("json", data_files=dataset_path, split="train")

    # 2. Define wrapper reward function matching TRL expectance
    def trl_reward_function(prompts, completions, **kwargs) -> List[float]:
        """TRL GRPOTrainer reward callback."""
        rewards = []
        for prompt_str, completion_str in zip(prompts, completions):
            # Attempt to parse data back from prompt_str
            # Prompt str contains: "quant_signals: ... \n\n performance_context: ... "
            # Extract actual_trade_outcome from dataset if passed, or default
            try:
                # Reconstruct prompt data dictionary
                prompt_data = {}
                # Match quant_signals block
                signals_match = re.search(r"quant_signals:\s*(\{.*?\})", prompt_str, re.DOTALL)
                if signals_match:
                    prompt_data["quant_signals"] = json.loads(signals_match.group(1))
                    
                perf_match = re.search(r"performance_context:\s*(\{.*?\})", prompt_str, re.DOTALL)
                if perf_match:
                    prompt_data["performance_context"] = json.loads(perf_match.group(1))
                    
                micro_match = re.search(r"market_microstructure:\s*(\{.*?\})", prompt_str, re.DOTALL)
                if micro_match:
                    prompt_data["market_microstructure"] = json.loads(micro_match.group(1))
                    
                struct_match = re.search(r"structure_context:\s*(\{.*?\})", prompt_str, re.DOTALL)
                if struct_match:
                    prompt_data["structure_context"] = json.loads(struct_match.group(1))
                
                # Check outcome: wins have positive EV, losses negative EV in reconstructed prompt
                ev = prompt_data.get("performance_context", {}).get("ev_per_trade", 0.0)
                prompt_data["actual_trade_outcome"] = "WIN" if ev > 0 else "LOSS"
                
                r = reward_fn(prompt_data, completion_str)
                rewards.append(r)
            except Exception as e:
                logger.error(f"Error evaluating reward: {e}")
                rewards.append(0.0)
        return rewards

    # 3. Configure TRL GRPO Config
    training_args = GRPOConfig(
        output_dir="models/qwen-1.5b-trading-analyst",
        learning_rate=5e-6,
        adam_beta1=0.9,
        adam_beta2=0.99,
        weight_decay=0.1,
        warmup_ratio=0.1,
        lr_scheduler_type="cosine",
        logging_steps=1,
        bf16=torch.cuda.is_bf16_supported(),
        fp16=not torch.cuda.is_bf16_supported(),
        num_train_epochs=1,
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        num_generations=8, # number of candidate generation runs per prompt for RL comparisons
        max_prompt_length=1024,
        max_completion_length=1024,
        save_strategy="steps",
        save_steps=50,
    )

    # 4. Initialize GRPOTrainer
    trainer = GRPOTrainer(
        model=model,
        reward_funcs=[trl_reward_function],
        args=training_args,
        train_dataset=dataset,
    )

    logger.info("Starting GRPO Reinforcement Learning Training...")
    trainer.train()
    
    # Save merged model weights
    logger.info("Training complete. Merging and saving model...")
    merged_path = "models/trading_analyst_merged"
    model.save_pretrained_merged(merged_path, tokenizer, save_method="merged_4bit")
    logger.info(f"LoRA adapters merged and saved to: {merged_path}")


if __name__ == "__main__":
    # If run directly, define a test run on mock data to verify reward checking
    mock_prompt_data = {
        "performance_context": {
            "reason_code_historical_win_rate": 62.0,
            "profit_factor": 1.95
        },
        "market_microstructure": {
            "volatility_regime": "TRENDING_UP",
            "current_spread": 12.0
        },
        "structure_context": {
            "htf_bias": "bullish",
            "ltf_trigger": "bos"
        },
        "actual_trade_outcome": "WIN"
    }
    
    mock_model_output = """
    <thought>
    The market is trending_up with a current spread of 12.0. Win rate is 62.0% and profit factor 1.95. HTF bias is bullish and we triggered on bos. Proceed.
    </thought>
    <verdict>
    {
      "model_agreement_count": "3/4",
      "historical_edge": "positive",
      "microstructure_quality": "clean",
      "structure_alignment": "confirming",
      "strongest_risk": "None.",
      "recommendation": "approve",
      "reason_code": "win_consensus"
    }
    </verdict>
    """
    
    print("Testing parser and reward checking functions on mock input:")
    score = reward_fn(mock_prompt_data, mock_model_output)
    print(f"  Mock parse output thought: '{parse_output(mock_model_output)[0]}'")
    print(f"  Mock parse output verdict: {parse_output(mock_model_output)[1]}")
    print(f"  Grounding Reward  : {grounding_check(parse_output(mock_model_output)[0], mock_prompt_data)}")
    print(f"  Calibration Reward: {calibration_check(parse_output(mock_model_output)[1], mock_prompt_data['performance_context'])}")
    print(f"  Structure Reward  : {structure_check(parse_output(mock_model_output)[1], mock_prompt_data['structure_context'])}")
    print(f"  Outcome Reward    : {outcome_check(parse_output(mock_model_output)[1], mock_prompt_data['actual_trade_outcome'])}")
    print(f"  Total GRPO Reward : {score:.4f} (Max possible: 1.0)")
