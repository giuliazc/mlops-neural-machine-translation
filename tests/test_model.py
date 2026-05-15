import pytest
import tensorflow as tf
from ml.model import (
    _positional_encoding,
    _padding_mask,
    _causal_mask,
    PositionalEmbedding,
    TransformerConfig,
    WarmupSchedule
)

def test_positional_encoding_shape():
    """Test that positional encoding returns correct shape."""
    length = 10
    depth = 64
    pos_enc = _positional_encoding(length, depth)
    assert pos_enc.shape == (1, length, depth)

def test_positional_encoding_values():
    """Test positional encoding produces different values per position."""
    pos_enc = _positional_encoding(5, 32)
    assert not tf.reduce_all(tf.equal(pos_enc[0, 0, :], pos_enc[0, 1, :]))

def test_padding_mask_zeros():
    """Test padding mask identifies zeros correctly."""
    x = tf.constant([[1, 2, 0], [3, 0, 0]])
    mask = _padding_mask(x)
    expected = tf.constant([[True, True, False], [True, False, False]])
    assert tf.reduce_all(tf.equal(mask, expected))

def test_causal_mask_shape():
    """Test causal mask shape."""
    length = tf.constant(5)
    mask = _causal_mask(length)
    assert mask.shape == (5, 5)

def test_causal_mask_values():
    """Test causal mask prevents future attention."""
    length = tf.constant(3)
    mask = _causal_mask(length)
    assert mask[0, 0] == True
    assert mask[0, 1] == False
    assert mask[0, 2] == False
    assert mask[2, 0] == True
    assert mask[2, 1] == True
    assert mask[2, 2] == True

def test_positional_embedding_initialization():
    """Test PositionalEmbedding layer initializes correctly."""
    layer = PositionalEmbedding(vocab_size=1000, d_model=128, max_len=64)
    assert layer.d_model == 128
    assert layer.embedding is not None

def test_positional_embedding_call():
    """Test PositionalEmbedding forward pass."""
    layer = PositionalEmbedding(vocab_size=1000, d_model=128, max_len=64)
    x = tf.constant([[1, 2, 3], [4, 5, 0]])
    output = layer(x)
    assert output.shape == (2, 3, 128)

def test_positional_embedding_mask_zero():
    """Test PositionalEmbedding respects mask_zero."""
    layer = PositionalEmbedding(vocab_size=100, d_model=64, max_len=32)
    x = tf.constant([[1, 2, 0]])
    mask = layer.compute_mask(x)
    assert mask.numpy()[0, 2] == False

def test_transformer_config_required_args():
    """Test TransformerConfig requires vocab sizes and max_tokens."""
    config = TransformerConfig(
        pt_vocab_size=5000,
        en_vocab_size=5000,
        max_tokens=64
    )
    assert config.num_layers == 4  # Default value
    assert config.d_model == 128  # Default value
    assert config.num_heads == 4  # Default value

def test_transformer_config_custom():
    """Test TransformerConfig with custom values."""
    config = TransformerConfig(
        pt_vocab_size=3000,
        en_vocab_size=3000,
        max_tokens=32,
        num_layers=2,
        d_model=64,
        num_heads=2,
        dff=256,
        dropout=0.1
    )
    assert config.num_layers == 2
    assert config.d_model == 64
    assert config.pt_vocab_size == 3000

def test_warmup_schedule_low_step():
    """Test WarmupSchedule for early steps."""
    schedule = WarmupSchedule(d_model=128)
    lr_1 = schedule(1)
    lr_100 = schedule(100)
    assert lr_100 > lr_1

def test_warmup_schedule_values_positive():
    """Test WarmupSchedule always returns positive values."""
    schedule = WarmupSchedule(d_model=256)
    for step in [1, 100, 1000, 10000]:
        lr = schedule(step)
        assert lr > 0
