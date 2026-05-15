import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from ml.tokenizers import (
    get_start_end_ids,
    vocab_size,
    _require_tf_text
)

def test_require_tf_text_ok():
    """Test that _require_tf_text passes when tensorflow_text is available."""
    with patch("ml.tokenizers._TF_TEXT_OK", True):
        _require_tf_text()  # Should not raise

def test_require_tf_text_fails():
    """Test that _require_tf_text raises when tensorflow_text is not available."""
    with patch("ml.tokenizers._TF_TEXT_OK", False):
        with pytest.raises(RuntimeError, match="tensorflow-text é necessário"):
            _require_tf_text()

def test_get_start_end_ids():
    """Test extracting start and end token IDs from tokenizer."""
    mock_tokenizer = Mock()
    
    # Mock the return of tf.Tensor
    mock_token_0 = Mock()
    mock_token_0.numpy.return_value = 101
    mock_token_1 = Mock()
    mock_token_1.numpy.return_value = 102
    
    mock_tokenizer.tokenize.return_value = [[mock_token_0, mock_token_1]]
    
    start_id, end_id = get_start_end_ids(mock_tokenizer)
    assert start_id == 101
    assert end_id == 102
    mock_tokenizer.tokenize.assert_called_once_with([""])

def test_vocab_size():
    """Test retrieving vocabulary size from tokenizer."""
    mock_tokenizer = Mock()
    
    mock_vocab = Mock()
    mock_vocab.numpy.return_value = 5000
    mock_tokenizer.get_vocab_size.return_value = mock_vocab
    
    result = vocab_size(mock_tokenizer)
    assert result == 5000
    mock_tokenizer.get_vocab_size.assert_called_once()
