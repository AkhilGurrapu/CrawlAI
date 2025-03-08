import os
import json
import time
import hashlib
import difflib
from datetime import datetime

HISTORY_DIR = "crawled_content/history"

# Create directory for storing document history
os.makedirs(HISTORY_DIR, exist_ok=True)

class DocumentHistory:
    def __init__(self):
        self.history_index = {}
        self.load_history_index()
    
    def load_history_index(self):
        """Load the history index from disk"""
        index_path = os.path.join(HISTORY_DIR, 'history_index.json')
        if os.path.exists(index_path):
            try:
                with open(index_path, 'r') as f:
                    self.history_index = json.load(f)
                print(f"Loaded history index with {len(self.history_index)} documents")
            except Exception as e:
                print(f"Error loading history index: {e}")
                self.history_index = {}
    
    def save_history_index(self):
        """Save the history index to disk"""
        index_path = os.path.join(HISTORY_DIR, 'history_index.json')
        try:
            with open(index_path, 'w') as f:
                json.dump(self.history_index, f)
        except Exception as e:
            print(f"Error saving history index: {e}")
    
    def compute_content_hash(self, content):
        """Compute a hash of the content for quick comparison"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def track_document(self, url, title, content, language="en"):
        """Track a document, saving a new version if content has changed"""
        # Create a safe filename from the URL
        safe_url = url.replace('://', '_').replace('/', '_').replace('?', '_').replace('&', '_')
        
        # Compute content hash
        content_hash = self.compute_content_hash(content)
        
        # Check if we already have this document in our index
        if url in self.history_index:
            # Check if content has changed by comparing hash
            if self.history_index[url]['latest_hash'] == content_hash:
                # Content hasn't changed, no need to save a new version
                return False
        
        # Initialize document in index if it's new
        if url not in self.history_index:
            self.history_index[url] = {
                'versions': [],
                'latest_hash': None
            }
        
        # Create a new version entry
        timestamp = time.time()
        version_id = f"{safe_url}_{timestamp}"
        version_data = {
            'version_id': version_id,
            'timestamp': timestamp,
            'date': datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S'),
            'title': title,
            'hash': content_hash,
            'language': language
        }
        
        # Add to versions list
        self.history_index[url]['versions'].append(version_data)
        self.history_index[url]['latest_hash'] = content_hash
        
        # Save the content to a version file
        version_path = os.path.join(HISTORY_DIR, f"{version_id}.txt")
        try:
            with open(version_path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            print(f"Error saving version content: {e}")
            return False
        
        # Update the index file
        self.save_history_index()
        
        return True
    
    def get_document_versions(self, url):
        """Get all versions of a document"""
        if url in self.history_index:
            return self.history_index[url]['versions']
        return []
    
    def get_version_content(self, version_id):
        """Get the content of a specific version"""
        version_path = os.path.join(HISTORY_DIR, f"{version_id}.txt")
        if os.path.exists(version_path):
            try:
                with open(version_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                print(f"Error reading version content: {e}")
        return None
    
    def compare_versions(self, version_id1, version_id2):
        """Compare two versions and return a diff"""
        content1 = self.get_version_content(version_id1)
        content2 = self.get_version_content(version_id2)
        
        if content1 is None or content2 is None:
            return None
        
        # Generate a unified diff
        diff = difflib.unified_diff(
            content1.splitlines(),
            content2.splitlines(),
            lineterm='',
            n=3  # Context lines
        )
        
        return '\n'.join(diff)
    
    def process_content_store(self, content_store):
        """Process a content store and track all documents"""
        updated_count = 0
        for url, data in content_store.items():
            if self.track_document(url, data['title'], data['content'], data.get('language', 'en')):
                updated_count += 1
        
        return updated_count
    
    def get_document_history_summary(self, url):
        """Get a summary of document history"""
        if url not in self.history_index:
            return None
        
        versions = self.history_index[url]['versions']
        if not versions:
            return None
        
        # Sort versions by timestamp (newest first)
        sorted_versions = sorted(versions, key=lambda x: x['timestamp'], reverse=True)
        
        # Get the latest version content
        latest_content = self.get_version_content(sorted_versions[0]['version_id'])
        
        return {
            'url': url,
            'title': sorted_versions[0]['title'],
            'version_count': len(versions),
            'latest_version': sorted_versions[0],
            'first_version': sorted_versions[-1],
            'latest_content': latest_content,
            'all_versions': sorted_versions
        }