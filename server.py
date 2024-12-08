from flask import Flask, request, jsonify
import os
from flask_cors import CORS
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.preprocessing import StandardScaler
import pickle
import os

class ECGProcessor:
    def __init__(self, model_path, scaler_path, chunk_size=5000, overlap=0):
        """
        Initialize ECG processor
        
        Args:
            model_path: Path to saved Random Forest model
            scaler_path: Path to saved StandardScaler
            chunk_size: Size of ECG chunks to process (default 5000)
            overlap: Number of samples to overlap between chunks (default 0)
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)
        with open(scaler_path, 'rb') as f:
            self.scaler = pickle.load(f)
            
    def parse_ecg_data(self, raw_data):
        lines = raw_data.split('\n')
        data_values = []
        data_started = False
        
        for line in lines:
            if line.strip() == '':
                continue
            # Skip header until we find numeric data
            if not data_started:
                try:
                    num = float(line.strip(','))
                    if num >= -1 and num <= 1:
                        data_started = True
                except ValueError:
                    continue
            if data_started:
                try:
                    value = float(line.strip(','))
                    data_values.append(value)
                except ValueError:
                    continue
                    
        return np.array(data_values)
    
    def extract_statistical_features(self, chunk):
        features = []
        
        # Time domain statistical features
        features.extend([
            np.mean(chunk),
            np.std(chunk),
            stats.skew(chunk),
            stats.kurtosis(chunk),
            np.ptp(chunk)
        ])
        
        return np.array(features)
    
    def get_chunks(self, data):
        chunks = []
        step = self.chunk_size - self.overlap
        
        for i in range(0, len(data) - self.chunk_size + 1, step):
            chunk = data[i:i + self.chunk_size]
            chunks.append(chunk)
            
        return chunks
    
    def process_and_predict(self, ecg_data):
        try:
            data = self.parse_ecg_data(ecg_data)
            chunks = self.get_chunks(data)
            
            if not chunks:
                raise ValueError("Not enough data for analysis")
            
            # Process each chunk
            predictions = []
            for chunk in chunks:
                features = self.extract_statistical_features(chunk)
                features = features.reshape(1, -1)
                features_scaled = self.scaler.transform(features)
                pred = self.model.predict(features_scaled)[0]
                predictions.append(pred)
            
            # Get mode of predictions
            prediction_counts = pd.Series(predictions).value_counts()
            final_predictions = prediction_counts.index.tolist()
            
            return {
                'predictions': final_predictions,
                'counts': prediction_counts.tolist(),
                'chunks_processed': len(chunks)
            }
            
        except Exception as e:
            raise RuntimeError(f"Error processing ECG data: {str(e)}")
        
app = Flask(__name__)
CORS(app)

CSV_DIR = 'csv_files'

if not os.path.exists(CSV_DIR):
    os.makedirs(CSV_DIR)

@app.route('/process_ecg', methods=['POST'])
def process_ecg():
    try:
        ecg_data = request.json['ecgData']
        model_path = os.path.join('assets', 'model_assets', 'random_forest_model.pkl')
        scaler_path = os.path.join('assets', 'model_assets', 'scaler.pkl')
        
        processor = ECGProcessor(
            model_path=model_path,
            scaler_path=scaler_path
        )
        results = processor.process_and_predict(ecg_data)
        
        return jsonify({
            'emotions': results['predictions'],
            'counts': results['counts'],
            'chunks_processed': results['chunks_processed']
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)