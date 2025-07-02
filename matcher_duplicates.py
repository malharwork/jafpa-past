import json
import numpy as np
from openai import OpenAI
from typing import List, Dict, Tuple
import os
from tqdm import tqdm
from dotenv import load_dotenv
import nltk
from nltk.corpus import stopwords
import re

# Download required NLTK data
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

# Load environment variables from .env file
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=api_key)

# Get basic stop words and add custom ones
STOP_WORDS = set(stopwords.words('english'))
CUSTOM_STOP_WORDS = {
    'fresh', 'juicy', 'delicious', 'tasty', 'premium', 'best', 'sourced', 
    'cleaned', 'hygienic', '100%', 'order', 'try', 'now', 'quality',
    'from', 'our', 'your', 'we', 
    
    'big', 'mini', 'fresh', 'quality', 'pack', 
    'pieces', 'piece', 'large', 'small', 'medium', 

    'supreme', 'net', 'g', 'gm', 'grams', 
    'juicy', 'tender', 'succulent', 'delicious', 'meaty', 
    'rich', 'smooth', 'tasty', 'comforting', 'ready', 'clean', 
    'cleaned', 'hygienic', 'flavorful', 'savoury', 'wholesome', 
    'superior', 'indulgent', 'favourite', 'authentic', 'classic', 
    'perfect', 'delightful', 'mouthwatering', 'amazing', 'special', 
    'everyday',
    'japfa' , 'licious', 'japfa best', 'own farms', 'biosecure', 
    'sourced', 'farm', 'raised', 'processing', 'center', 'centre', 
    'delivered', 'organic', 'nutritious', 'healthy', 'nutrient', 
    'nutrient-rich', 'nutrient-dense', 'nutrient-packed', 'nutrient-filled', 
    'nutrient-loaded', 'nutrient-enhanced', 'nutrient-boosted', 
    'nutrient-rich', 'nutrient-dense', 'nutrient-packed', 'nutrient-filled', 
    'nutrient-loaded', 'nutrient-boosted', 'nutrient-rich', 'nutrient-dense', 
}
ALL_STOP_WORDS = STOP_WORDS.union(CUSTOM_STOP_WORDS)

def preprocess_text(text: str) -> str:
    """Clean and preprocess text by removing stop words and special characters"""
    # Convert to lowercase
    text = text.lower()
    
    # Remove special characters and digits
    text = re.sub(r'[^a-zA-Z\s]', ' ', text)
    
    # Split into words
    words = text.split()
    
    # Remove stop words and custom words
    words = [word for word in words if word not in ALL_STOP_WORDS]
    
    # Join words back together
    return ' '.join(words)

def load_json_data(file_path: str) -> List[Dict]:
    """Load JSON data from file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_embedding(text: str) -> List[float]:
    """Get embedding for a text using OpenAI's API"""
    # Preprocess text before getting embedding
    cleaned_text = preprocess_text(text)
    if not cleaned_text.strip():  # If text is empty after preprocessing
        cleaned_text = text  # Use original text
    
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=cleaned_text
    )
    return response.data[0].embedding

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Calculate cosine similarity between two vectors"""
    v1_array = np.array(v1)
    v2_array = np.array(v2)
    return np.dot(v1_array, v2_array) / (np.linalg.norm(v1_array) * np.linalg.norm(v2_array))

def get_top_matches(source_item: Dict, target_items: List[Dict], 
                   source_embedding: List[float], target_embeddings: List[List[float]], 
                   top_k: int = 3) -> List[Tuple[Dict, float]]:
    """Get top k matches for a source item"""
    similarities = [cosine_similarity(source_embedding, target_emb) for target_emb in target_embeddings]
    top_indices = np.argsort(similarities)[-top_k:][::-1]
    return [(target_items[idx], similarities[idx]) for idx in top_indices]

def get_weighted_embedding(title: str, description: str, product_type: str, 
                       title_weight: float = 0.5, 
                       type_weight: float = 0.3,
                       description_weight: float = 0.2) -> List[float]:
    """Get weighted embedding combining title, type and description with specified weights"""
    # Get individual embeddings
    title_embedding = np.array(get_embedding(title))
    type_embedding = np.array(get_embedding(product_type))
    desc_embedding = np.array(get_embedding(description))
    
    # Combine embeddings with weights
    weighted_embedding = (title_weight * title_embedding) + \
                        (type_weight * type_embedding) + \
                        (description_weight * desc_embedding)
    
    # Normalize the weighted embedding
    weighted_embedding = weighted_embedding / np.linalg.norm(weighted_embedding)
    
    return weighted_embedding.tolist()

def match_products(source_items: List[Dict], target_items: List[Dict], 
                  match_type: str = 'title') -> Dict[str, List[Dict]]:
    """Match products based on specified criteria"""
    print(f"\nGenerating embeddings for {match_type}...")
    
    # Generate embeddings for source items
    source_embeddings = []
    for item in tqdm(source_items, desc="Processing source items"):
        if match_type == 'title':
            text = item['title']
            source_embeddings.append(get_embedding(text))
        elif match_type == 'description':
            text = item['description']
            source_embeddings.append(get_embedding(text))
        elif match_type == 'weighted':
            source_embeddings.append(get_weighted_embedding(
                item['title'], 
                item['description'],
                item['type']
            ))
        else:  # combined
            text = f"{item['title']} {item['description']}"
            source_embeddings.append(get_embedding(text))
    
    # Generate embeddings for target items
    target_embeddings = []
    for item in tqdm(target_items, desc="Processing target items"):
        if match_type == 'title':
            text = item['title']
            target_embeddings.append(get_embedding(text))
        elif match_type == 'description':
            text = item['description']
            target_embeddings.append(get_embedding(text))
        elif match_type == 'weighted':
            target_embeddings.append(get_weighted_embedding(
                item['title'], 
                item['description'],
                item['type']
            ))
        else:  # combined
            text = f"{item['title']} {item['description']}"
            target_embeddings.append(get_embedding(text))
    
    # Find matches for each source item
    results = {}
    for idx, source_item in enumerate(tqdm(source_items, desc="Finding matches")):
        # Create a unique key using japfa_id
        key = source_item['japfa_id']
        
        matches = get_top_matches(source_item, target_items, source_embeddings[idx], target_embeddings)
        results[key] = {
            'japfa_product': {
                'title': source_item['title'],
                'category_name': source_item['category_name'],
                'type': source_item['type']
            },
            'matches': [
                {
                    'licious_id': match[0]['licious_id'],
                    'title': match[0]['title'],
                    'type': match[0]['type'],
                    'category_name': match[0]['category_name'],
                    'confidence': f"{match[1] * 100:.2f}%"
                }
                for match in matches
            ]
        }
    
    return results

def main():
    # Load data
    japfa_data = load_json_data('japfa_pune_2025_04_14_17_49_23_revised_description.json')
    licious_data = load_json_data('licious_pune_2025_04_14_17_09_46_revised_description.json')
    
    # Match products using weighted approach (50% title, 30% type, 20% description)
    print("\nMatching products...")
    weighted_matches = match_products(japfa_data, licious_data, 'weighted')
    
    # Save results
    results = {
        'weighted_matches': weighted_matches
    }
    
    with open('product_matches.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print("\nResults have been saved to 'product_matches.json'")

if __name__ == "__main__":
    main() 