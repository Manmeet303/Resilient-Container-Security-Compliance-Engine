from shared.utils.hashing import compute_layer_hash, compute_image_hash

def test_layer_hash_deterministic():
    assert compute_layer_hash("sha256:abc") == compute_layer_hash("sha256:abc")

def test_different_layers_different_hashes():
    assert compute_layer_hash("layer1") != compute_layer_hash("layer2")

def test_image_hash_order_independent():
    assert compute_image_hash(["a","b","c"]) == compute_image_hash(["c","a","b"])
