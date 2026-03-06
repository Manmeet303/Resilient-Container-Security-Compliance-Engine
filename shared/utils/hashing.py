import hashlib
from typing import List

def compute_layer_hash(layer_id: str) -> str:
    return hashlib.sha256(layer_id.encode("utf-8")).hexdigest()

def compute_image_hash(layer_ids: List[str]) -> str:
    combined = "|".join(sorted(layer_ids))
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()
