
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




def test_classify_attributes_with_prototypes(mock_clip_components):
    """Test that prototypes boost the score of an attribute."""
    from PIL import Image
    img = Image.new("RGB", (100, 100))
    
    # Mock text embeddings: orthogonal to image (dim 1)
    # Shape: (8, 77) -> (8, 512)
    def encode_text_side_effect(tokens):
        res = torch.zeros((tokens.shape[0], 512))
        res[:, 1] = 1.0 # Orthogonal to image (which is in dim 0)
        return res
        
    mock_clip_components.model.encode_text.side_effect = encode_text_side_effect
    
    # Mock image embedding: unit vector in dimension 0
    # Shape: (1, 512)
    with patch("app.services.vision._get_attribute_prototypes") as mock_get_protos:
        # Create a prototype for "top_light" that matches the image perfect (dim 0)
        proto_vec = torch.zeros(512)
        proto_vec[0] = 1.0
        
        # Determine image embedding to also be dim 0
        def encode_image_side_effect(img_tensor):
            vec = torch.zeros((1, 512))
            vec[0, 0] = 1.0
            return vec
        
        mock_clip_components.model.encode_image.side_effect = encode_image_side_effect
        
        # The function calls _get_attribute_prototypes(session, attribute)
        # We want to return { "top_light": proto_vec } when attribute="lighting"
        def get_protos_side_effect(session, attribute):
            if attribute == "lighting":
                return {"top_light": proto_vec}
            return {}
            
        mock_get_protos.side_effect = get_protos_side_effect
        
        with patch("torch.no_grad"):
            results = vision.classify_attributes_with_clip(img, session=MagicMock())
            
        # Text score = 0. Prototype match = 1.0. Mixed = 0.6*0 + 0.4*1 = 0.4
        # Threshold logic in lighting: max(0.2, best*0.85). Best is 0.4.
        lighting_results = [r for r in results if r.attribute == "lighting"]
        
        # "top_light" should be present with confidence ~0.4
        top_light = next((r for r in lighting_results if r.value == "top_light"), None)
        assert top_light is not None
        assert abs(top_light.confidence - 0.4) < 0.01
