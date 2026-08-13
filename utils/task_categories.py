# maps a task folder to the paper's misalignment category, used for the results path.

TASK_CATEGORY: dict[str, str] = {
    "misrep_finance": "strategic_misrep",
    "misrep_evaluation": "strategic_misrep",
    "tampering": "shutdown_tampering",
    "alignment_faking": "alignment_faking",
    "exfiltration_transfer": "model_exfiltration",
    "exfiltration_deletion": "model_exfiltration",
}


def task_category(task_name: str) -> str:
    """Return the paper category for a task folder.

    Memory variants share their base task's category, so misrep_evaluation_memory
    resolves to strategic_misrep like misrep_evaluation does.
    """
    base = task_name.removesuffix("_memory")
    if base not in TASK_CATEGORY:
        raise ValueError(f"Unknown task for category mapping: {task_name}")
    return TASK_CATEGORY[base]
