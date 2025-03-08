import streamlit as st
import json
import os
import requests
import sys
from urllib.parse import urlparse
from datetime import datetime

# Add the current directory to the path so we can import the SafeCrawler class
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app import SafeCrawler
from document_history import DocumentHistory

# Configure page
st.set_page_config(
    page_title="Web Crawler & Documentation Chat",
    page_icon="🕸️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    /* Main container styling */
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        max-width: 100%;
    }
    
    /* Sidebar styling */
    .sidebar .sidebar-content {
        background-color: #f8fafc;
        padding: 1rem 0.5rem;
    }
    
    /* Make sidebar wider */
    [data-testid="stSidebar"] {
        min-width: 350px !important;
        max-width: 450px !important;
    }
    
    /* Card styling */
    .stCard {
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        padding: 1rem;
        margin-bottom: 1rem;
        background-color: #ffffff;
        border: 1px solid #e5e7eb;
    }
    
    /* Button styling */
    .stButton button {
        border-radius: 8px;
        font-weight: 500;
        width: 100%;
        height: auto;
        padding: 0.5rem;
        white-space: normal;
        word-wrap: break-word;
    }
    
    /* Header styling */
    h1, h2, h3 {
        font-weight: 700 !important;
        color: #1E3A8A !important;
        margin-bottom: 1rem !important;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    /* Input field styling */
    .stTextInput input, .stNumberInput input, .stTextArea textarea {
        border-radius: 8px;
        border: 1px solid #E5E7EB;
        padding: 0.5rem;
    }
    
    /* Chat message styling */
    .stChatMessage {
        margin-bottom: 1rem !important;
        overflow-wrap: break-word;
        word-wrap: break-word;
        word-break: break-word;
    }
    
    /* Custom document card */
    .document-card {
        background-color: #f8fafc;
        border-radius: 10px;
        padding: 12px;
        margin-bottom: 12px;
        border-left: 4px solid #3B82F6;
        overflow-wrap: break-word;
        word-wrap: break-word;
        word-break: break-word;
    }
    
    /* Document list styling */
    .document-list {
        margin-top: 10px;
    }
    
    .document-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 12px;
        margin-bottom: 8px;
        background-color: #f8fafc;
        border-radius: 8px;
        border: 1px solid #e5e7eb;
    }
    
    .document-item:hover {
        background-color: #eff6ff;
    }
    
    .document-url {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        flex-grow: 1;
        margin-right: 10px;
    }
    
    .document-actions {
        flex-shrink: 0;
    }
    
    /* Custom search box */
    .search-box {
        background-color: #f8fafc;
        border-radius: 10px;
        padding: 12px;
        margin-bottom: 12px;
        border: 1px solid #e5e7eb;
    }
    
    /* Empty state styling */
    .empty-state {
        text-align: center;
        padding: 2rem;
        background-color: #f8fafc;
        border-radius: 10px;
        margin: 1rem 0;
    }
    
    /* Welcome message styling */
    .welcome-message {
        text-align: center;
        padding: 1rem;
        background-color: #f0f9ff;
        border-radius: 10px;
        margin-bottom: 1rem;
        border-left: 4px solid #3B82F6;
    }
    
    /* Simple chat container */
    .simple-chat-container {
        background-color: #f8fafc;
        border-radius: 10px;
        border: 1px solid #e5e7eb;
        padding: 1rem;
        margin-bottom: 1rem;
        height: 300px;
        overflow-y: auto;
    }
    
    /* Fix for text overflow */
    div[data-testid="stText"], 
    div[data-testid="stMarkdown"] p {
        overflow-wrap: break-word;
        word-wrap: break-word;
        word-break: break-word;
        white-space: pre-wrap;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "content_store" not in st.session_state:
    st.session_state.content_store = {}
    
if "crawl_status" not in st.session_state:
    st.session_state.crawl_status = None
    
if "crawl_progress" not in st.session_state:
    st.session_state.crawl_progress = 0
    
if "crawl_complete" not in st.session_state:
    st.session_state.crawl_complete = False
    
if "doc_history" not in st.session_state:
    st.session_state.doc_history = DocumentHistory()
    
if "error_log" not in st.session_state:
    st.session_state.error_log = []

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

# Load the crawled content
def load_content():
    content_path = os.path.join("crawled_content", "content_store.json")
    
    try:
        with open(content_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Error loading content: {e}")
        return {}

# Log errors to session state
def log_error(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.error_log.append(f"[{timestamp}] {message}")

# Search relevant content
def search_relevant_content(query, content_store, max_results=5):
    results = []
    for url, page_data in content_store.items():
        content = page_data["content"]
        title = page_data["title"]
        
        # Simple keyword matching
        query_terms = query.lower().split()
        relevance = sum(1 for term in query_terms if term in content.lower())
        
        if relevance > 0:
            results.append((url, title, content, relevance))
    
    results.sort(key=lambda x: x[3], reverse=True)
    return results[:max_results]

# Configure Gemini API access
def generate_gemini_response(prompt, api_key="AIzaSyBxM67tT5HdLKMuhsaj-jLHox7Yi2nbRYQ"):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key
    }
    data = {
        "contents": [{"parts":[{"text": prompt}]}]
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        else:
            error_msg = f"API Error: {response.status_code} - {response.text}"
            log_error(error_msg)
            return f"Sorry, I encountered an error when trying to generate a response. Error details: {error_msg}"
    except Exception as e:
        error_msg = f"Error calling Gemini API: {str(e)}"
        log_error(error_msg)
        return f"Sorry, I encountered an error when trying to generate a response. Error details: {error_msg}"

# Function to start the crawling process
def start_crawl(url, max_depth, keyword, max_links):
    st.session_state.crawl_status = "in_progress"
    st.session_state.crawl_progress = 0
    st.session_state.crawl_complete = False
    
    # Create crawler instance
    crawler = SafeCrawler()
    
    # Create a progress bar placeholder
    progress_placeholder = st.empty()
    progress_bar = progress_placeholder.progress(0)
    progress_text = st.empty()
    
    def progress_callback(current_url, links_crawled, total_links):
        """Callback to update progress during crawl"""
        progress = min(links_crawled / total_links, 1.0)
        st.session_state.crawl_progress = progress
        progress_bar.progress(progress)
        progress_text.text(f"{int(progress * 100)}% completed")
    
    try:
        # Start the crawl
        new_content = crawler.crawl(
            start_url=url,
            max_depth=max_depth,
            keyword=keyword,
            max_links=max_links,
            progress_callback=progress_callback
        )
        
        # Merge new content with existing content instead of replacing
        if 'content_store' in st.session_state and st.session_state.content_store:
            # Update existing content store with new content
            st.session_state.content_store.update(new_content)
            merged_content = st.session_state.content_store
        else:
            # If no existing content, just use the new content
            merged_content = new_content
            st.session_state.content_store = merged_content
        
        # Update session state
        st.session_state.crawl_status = "complete"
        st.session_state.crawl_complete = True
        st.session_state.crawl_progress = 1.0
        
        # Update progress UI
        progress_bar.progress(1.0)
        progress_text.text(f"100% completed - Added {len(new_content)} pages")
        
        # Save the merged content to disk
        os.makedirs("crawled_content", exist_ok=True)
        with open(os.path.join("crawled_content", "content_store.json"), "w") as f:
            json.dump(merged_content, f)
        
        # Process document history
        st.session_state.doc_history.process_content_store(new_content)
        
        return merged_content
    except Exception as e:
        error_message = f"Error during crawl: {str(e)}"
        log_error(error_message)
        st.session_state.crawl_status = "error"
        progress_text.text(f"Error: {error_message}")
        return None

# Function to delete a document
def delete_document(url):
    try:
        if url in st.session_state.content_store:
            del st.session_state.content_store[url]
            
            # Save updated content store
            with open(os.path.join("crawled_content", "content_store.json"), 'w') as f:
                json.dump(st.session_state.content_store, f)
            
            return True
        return False
    except Exception as e:
        log_error(f"Error deleting document: {e}")
        return False

# Function to reset crawl data
def reset_crawl_data():
    try:
        # Reset session state
        st.session_state.content_store = {}
        st.session_state.crawl_status = None
        st.session_state.crawl_progress = 0
        st.session_state.crawl_complete = False
        
        # Clear content store file
        os.makedirs("crawled_content", exist_ok=True)
        with open(os.path.join("crawled_content", "content_store.json"), 'w') as f:
            json.dump({}, f)
        
        # Clear chat history
        st.session_state.chat_messages = []
        
        return True
    except Exception as e:
        log_error(f"Error resetting crawl data: {e}")
        return False

def main():
    # Load saved content if exists
    if 'content_store' not in st.session_state or not st.session_state.content_store:
        content_store = load_content()
        if content_store:
            st.session_state.content_store = content_store
    
    # Sidebar - Document Management
    with st.sidebar:
        st.title("🕸️ Web Crawler")
        
        # Crawler section
        with st.container():
            st.markdown('<div class="search-box">', unsafe_allow_html=True)
            url = st.text_input("Enter URL to crawl", "", 
                               placeholder="Enter a URL to crawl")
            
            col1, col2 = st.columns(2)
            with col1:
                max_depth = st.slider("Max depth", 1, 5, 2)
            with col2:
                max_links = st.slider("Max links", 1, 50, 10)
            
            keyword = st.text_input("Filter by keyword", "", 
                                  placeholder="Optional keyword filter")
            
            # Crawl buttons
            crawl_col1, crawl_col2 = st.columns(2)
            with crawl_col1:
                start_button = st.button("Start Crawling", type="primary", use_container_width=True)
                if start_button and url:  # Only start crawling if URL is provided
                    content_store = start_crawl(url, max_depth, keyword if keyword else None, max_links)
                    if content_store:
                        st.success(f"Added new pages to your collection")
                elif start_button and not url:
                    st.error("Please enter a URL to crawl")
            
            with crawl_col2:
                if st.button("Reset Data", type="secondary", use_container_width=True):
                    reset_crawl_data()
                    st.success("Data reset")
                    st.experimental_rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Document section
        st.markdown("---")
        st.subheader("📄 Documents")
        
        # Document stats
        content_store = st.session_state.content_store
        if content_store:
            # Show document count
            st.markdown(f"""
            <div class="document-card">
                <p>📚 <strong>{len(content_store)}</strong> documents in collection</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Search documents
            search_term = st.text_input("Search", "", placeholder="Search documents...", key="doc_search")
            
            # Filter documents based on search term
            filtered_docs = {}
            if search_term:
                for url, data in content_store.items():
                    if (search_term.lower() in url.lower() or 
                        search_term.lower() in data.get('title', '').lower() or
                        search_term.lower() in data.get('content', '').lower()):
                        filtered_docs[url] = data
            else:
                filtered_docs = content_store
            
            # Display document count
            if search_term:
                st.write(f"Showing {len(filtered_docs)} of {len(content_store)} documents")
            
            # Display documents in a scrollable container
            if filtered_docs:
                # Display each document as a simple row with URL and delete button
                for url, data in filtered_docs.items():
                    title = data.get('title', 'Untitled')
                    
                    # Create a row with columns for URL and delete button
                    col1, col2 = st.columns([9, 1])
                    
                    with col1:
                        st.markdown(f"<div style='padding: 8px; overflow: hidden; text-overflow: ellipsis;'><a href='{url}' target='_blank'>{title[:70] + '...' if len(title) > 70 else title}</a></div>", unsafe_allow_html=True)
                    
                    with col2:
                        if st.button("🗑️", key=f"delete_{url}"):
                            if delete_document(url):
                                st.success("Deleted!")
                                st.experimental_rerun()
                    
                    # Add a light separator
                    st.markdown("<hr style='margin: 0; border: 0; border-top: 1px solid #f0f0f0;'>", unsafe_allow_html=True)
            elif search_term:
                st.info(f"No documents found matching '{search_term}'")
        else:
            st.markdown("""
            <div class="empty-state">
                <p>No documents found</p>
                <p>Start crawling to collect documents</p>
            </div>
            """, unsafe_allow_html=True)
    
    # Main content - Chat
    st.title("💬 Chat with Documents")
    
    # Dynamic welcome message based on state
    if not st.session_state.chat_messages:
        if st.session_state.content_store:
            st.markdown("""
            <div class="welcome-message">
                <h3>👋 Welcome to Document Chat!</h3>
                <p>Your documents are ready. Ask any question about them below.</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="welcome-message">
                <h3>👋 Get Started</h3>
                <p>Enter a URL in the sidebar and click "Start Crawling" to begin.</p>
                <p>Once you have documents, you can chat with them here.</p>
            </div>
            """, unsafe_allow_html=True)
    
    # Chat messages
    if st.session_state.chat_messages:
        st.markdown('<div class="simple-chat-container">', unsafe_allow_html=True)
        for message in st.session_state.chat_messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Chat input
    if not st.session_state.content_store:
        st.warning("No documents available. Start crawling to chat with your documents.")
        chat_input_disabled = True
    else:
        chat_input_disabled = False
    
    # Chat input with proper spacing
    prompt = st.chat_input("Ask a question about the crawled content...", disabled=chat_input_disabled)
    
    if prompt:
        # Add user message to chat history
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        
        # Force a rerun to display the user message
        st.experimental_rerun()
    
    # Process chat response if there's a new user message
    if st.session_state.chat_messages and st.session_state.chat_messages[-1]["role"] == "user":
        prompt = st.session_state.chat_messages[-1]["content"]
        
        # Display assistant response with a spinner while processing
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            with st.spinner("Searching documents..."):
                if not st.session_state.content_store:
                    response = "No documents have been crawled yet. Please crawl some content first using the sidebar."
                else:
                    # Search for relevant content
                    relevant_content = search_relevant_content(prompt, st.session_state.content_store)
                    
                    if not relevant_content:
                        response = f"I couldn't find any relevant information about '{prompt}' in the crawled content."
                    else:
                        # Generate response using relevant content
                        context = "\n\n".join([f"Page: {title}\n{content[:1000]}..." for _, title, content, _ in relevant_content[:3]])
                        
                        try:
                            response = generate_gemini_response(
                                f"Answer the following question based on this context:\n\nContext: {context}\n\nQuestion: {prompt}"
                            )
                        except Exception as e:
                            response = f"Error generating response: {str(e)}\n\nHere's what I found in the documents:\n\n"
                            for i, (_, title, content, _) in enumerate(relevant_content[:3]):
                                response += f"**{title}**\n{content[:300]}...\n\n"
            
            # Display the response
            message_placeholder.markdown(response)
            
        # Add assistant response to chat history
        st.session_state.chat_messages.append({"role": "assistant", "content": response})

# Run the main function
if __name__ == "__main__":
    main()