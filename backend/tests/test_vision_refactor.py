
import pytest
from unittest.mock import MagicMock, patch
import torch
from app.services import vision


@pytest.fixture
def mock_clip_components():
    with patch("app.services.vision.get_clip_components") as mock_get:
        headers = MagicMock()
        headers.device = "cpu"
        
        # Mock model
        model = MagicMock()
        # Mock encode_image to return a constant vector [1.0, 0.0]
        model.encode_image.return_value = torch.tensor([[1.0, 0.0]])
        
        # Default side effect for encode_text: return vectors that align somewhat with image
        # Return [0.5, sqrt(1-0.5^2)] -> score 0.5
        def default_encoding_side_effect(text_tokens):
             batch_size = text_tokens.shape[0]
             # Return vectors with 0.6 similarity
             val = 0.6
             y = (1 - val**2)**0.5
             res = torch.zeros((batch_size, 2))
             res[:, 0] = val
             res[:, 1] = y
             return res

        model.encode_text.side_effect = default_encoding_side_effect
        headers.model = model
        
        def tokenizer_side_effect(prompts):
            return torch.zeros((len(prompts), 77), dtype=torch.long)
            
        headers.tokenizer = MagicMock(side_effect=tokenizer_side_effect)

        mock_get.return_value = headers
        yield headers

def test_classify_attributes_wiring(mock_clip_components):
    """Test that the function runs without error and returns attributes."""
    from PIL import Image
    img = Image.new("RGB", (100, 100))
    
    with patch("torch.no_grad"):
        results = vision.classify_attributes_with_clip(img)
    
    assert len(results) > 0
    categories = {r.attribute for r in results}
    assert "time_of_day" in categories
    assert "lighting" in categories
    assert "interior_exterior" in categories

def test_lighting_multi_label_logic(mock_clip_components):
    """Test that lighting can return multiple options if scores are close."""
    from PIL import Image
    img = Image.new("RGB", (100, 100))
    
    # Desired scores for lighting options
    desired_scores = [0.90, 0.88, 0.2, 0.1, 0.1, 0.1, 0.1, 0.1]
    
    def side_effect(tokens):
        # tokens shape is (N, 77). 
        if tokens.shape[0] == 8: 
             res = torch.zeros((8, 2))
             for i, s in enumerate(desired_scores):
                 y = (1 - s**2)**0.5
                 res[i, 0] = s
                 res[i, 1] = y
             return res
        return torch.tensor([[0.1, (1-0.1**2)**0.5]] * tokens.shape[0])

    mock_clip_components.model.encode_text.side_effect = side_effect
    
    with patch("torch.no_grad"):
        results = vision.classify_attributes_with_clip(img)
    
    lighting_results = [r for r in results if r.attribute == "lighting"]
    
    assert len(lighting_results) == 2
    values = {r.value for r in lighting_results}
    assert "hard_light" in values
    assert "soft_light" in values



