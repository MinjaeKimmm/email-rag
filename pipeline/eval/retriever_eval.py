import json
import os
import argparse
from typing import List, Dict
import numpy as np
from datetime import datetime
from tqdm import tqdm
from ..retrieval.pipeline import RetrievalPipeline, RetrieverType

def load_qa_pairs(qa_path: str) -> List[Dict]:
    """Load QA pairs from json file"""
    with open(qa_path, 'r') as f:
        return json.load(f)

def calculate_ndcg(retrieved_ids: List[str], ground_truth_id: str, k: int = 10) -> float:
    """Calculate NDCG score for a single query
    
    Args:
        retrieved_ids: List of conversation IDs in ranked order
        ground_truth_id: The correct conversation ID
        k: Number of top results to consider
        
    Returns:
        NDCG score between 0 and 1
    """
    # Limit to top k
    retrieved_ids = retrieved_ids[:k]
    
    # Calculate DCG
    dcg = 0
    for i, conv_id in enumerate(retrieved_ids):
        if conv_id == ground_truth_id:
            # Using log2(i + 2) because i is 0-based
            dcg += 1 / np.log2(i + 2)
            break
    
    # Calculate IDCG (best possible case where correct ID is first)
    idcg = 1  # 1/log2(2) = 1
    
    # If ground truth wasn't in top k, return 0
    if ground_truth_id not in retrieved_ids:
        return 0.0
    
    return dcg / idcg

def evaluate_retriever(
    qa_pairs: List[Dict],
    retriever_type: RetrieverType,
    start_idx: int = 0,
    end_idx: int = None,
    results_dir: str = "data/results",
    no_save: bool = False
) -> Dict:
    """Evaluate a retriever on QA pairs
    
    Args:
        qa_pairs: List of QA pairs with questions and ground truth conversation IDs
        retriever_type: Type of retriever to evaluate
        start_idx: Start index in qa_pairs
        end_idx: End index in qa_pairs (exclusive)
        results_dir: Directory to save results
        
    Returns:
        Dictionary with evaluation results
    """
    # Initialize pipeline
    pipeline = RetrievalPipeline()
    
    # Setup indices
    if end_idx is None:
        end_idx = len(qa_pairs)
    qa_pairs = qa_pairs[start_idx:end_idx]
    
    # Ensure results directory exists
    os.makedirs(results_dir, exist_ok=True)
    
    # Track results
    results = []
    ndcg_scores = []
    
    # Process each question with progress bar
    for qa_pair in tqdm(qa_pairs, ascii=True,desc=f"Evaluating {retriever_type} retriever"):
        query = qa_pair["Question"]
        ground_truth_id = qa_pair["Conversation_ID"]
        
        # Get retrieval results
        result = pipeline.retrieve(
            query=query,
            retriever_type=retriever_type,
            return_conversations=True,
            top_k=10
        )
        
        # Extract conversation IDs in ranked order
        if not result.conversation_groups:
            retrieved_ids = []
        else:
            conversations = sorted(
                result.conversation_groups.values(),
                key=lambda x: x.max_score,
                reverse=True
            )[:10]
            retrieved_ids = [conv.conversation_id for conv in conversations]
        
        # Calculate NDCG
        ndcg = calculate_ndcg(retrieved_ids, ground_truth_id)
        ndcg_scores.append(ndcg)
        
        # Store result
        results.append({
            "question": query,
            "ground_truth_id": ground_truth_id,
            "retrieved_ids": retrieved_ids,
            "ndcg": ndcg
        })
        
        # Save results periodically (every 10 queries) if not no_save
        if not no_save:
            current_idx = start_idx + len(results) - 1
            total_queries = end_idx - start_idx
            save_frequency = 10
            if len(results) % save_frequency == 0 or current_idx == end_idx - 1:
                # Calculate current average NDCG
                current_ndcg = np.mean(ndcg_scores)
                
                # Save main results file
                main_results = {
                    "retriever_type": retriever_type,
                    "start_idx": start_idx,
                    "end_idx": end_idx,
                    "current_progress": current_idx + 1,
                    "timestamp": datetime.now().isoformat(),
                    "average_ndcg": float(current_ndcg),
                    "results": results
                }
                
                # Save to main results file
                os.makedirs(results_dir, exist_ok=True)
                main_file = os.path.join(
                    results_dir,
                    f"{retriever_type}_{start_idx}_{end_idx}.json"
                )
                with open(main_file, 'w') as f:
                    json.dump(main_results, f, indent=2)
                
                # Save/update central results file
                central_file = os.path.join(results_dir, f"{retriever_type}_results.json")
                central_results = {
                    "total_queries": len(results),
                    "average_ndcg": float(current_ndcg)
                }
                with open(central_file, 'w') as f:
                    json.dump(central_results, f, indent=2)
    
    # Return final results
    return {
        "retriever_type": retriever_type,
        "start_idx": start_idx,
        "end_idx": end_idx,
        "timestamp": datetime.now().isoformat(),
        "average_ndcg": float(np.mean(ndcg_scores)),
        "results": results
    }
    
    return final_results

def main():
    parser = argparse.ArgumentParser(description="Evaluate retriever performance using NDCG")
    parser.add_argument(
        "--retriever",
        type=str,
        choices=["vector", "weighted", "multiplicative"],
        default="multiplicative",
        help="Type of retriever to evaluate"
    )
    parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="Start index in QA pairs"
    )
    parser.add_argument(
        "--end",
        type=int,
        help="End index in QA pairs (default: evaluate all)"
    )
    parser.add_argument(
        "--qa-file",
        type=str,
        default="data/qa_pairs.json",
        help="Path to QA pairs JSON file"
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        default="data/results",
        help="Directory to save results"
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not save results"
    )
    
    args = parser.parse_args()
    
    try:
        # Load QA pairs
        qa_pairs = load_qa_pairs(args.qa_file)
        
        # Run evaluation
        results = evaluate_retriever(
            qa_pairs=qa_pairs,
            retriever_type=args.retriever,
            start_idx=args.start,
            end_idx=args.end,
            results_dir=args.results_dir,
            no_save=args.no_save
        )
        
        # Print summary
        print(f"\nEvaluation Results for {args.retriever} retriever")
        print(f"Questions evaluated: {args.start} to {args.end if args.end else len(qa_pairs)}")
        print(f"Average NDCG: {results['average_ndcg']:.3f}")
        if not args.no_save:
            print(f"Results saved to: {args.results_dir}")
        
    except KeyboardInterrupt:
        msg = "\nEvaluation interrupted."
        if not args.no_save:
            msg += " Progress has been saved in the results directory."
        print(msg)
    except Exception as e:
        msg = f"\nError during evaluation: {e}"
        if not args.no_save:
            msg += "\nProgress has been saved in the results directory."
        print(msg)

def eval_retriever_simple(retriever_type: str = "weighted", start_idx: int = 0, end_idx: int = None, no_save: bool = False) -> Dict:
    """Simple wrapper to evaluate a retriever
    
    Args:
        retriever_type: Type of retriever ("vector", "weighted", "multiplicative")
        start_idx: Start index in QA pairs
        end_idx: End index in QA pairs (None = evaluate all)
        
    Returns:
        Dictionary with evaluation results
    """
    # Load QA pairs
    qa_pairs = load_qa_pairs("data/qa_pairs.json")
    
    # Run evaluation
    try:
        results = evaluate_retriever(
            qa_pairs=qa_pairs,
            retriever_type=retriever_type,
            start_idx=start_idx,
            end_idx=end_idx,
            no_save=no_save,
            results_dir="data/results"
        )
        print(f"\nEvaluation Results for {retriever_type} retriever")
        print(f"Questions evaluated: {start_idx} to {end_idx if end_idx else len(qa_pairs)}")
        print(f"Average NDCG: {results['average_ndcg']:.3f}")
        return results
        
    except KeyboardInterrupt:
        print("\nEvaluation interrupted. Progress has been saved in the results directory.")
        return None
    except Exception as e:
        print(f"\nError during evaluation: {e}")
        print("Progress has been saved in the results directory.")
        return None

if __name__ == "__main__":
    main()
