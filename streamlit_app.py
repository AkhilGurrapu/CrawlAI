import streamlit as st
import json
import os
import requests
import sys
from datetime import datetime
from urllib.parse import urlparse

# Add the current directory to the path so we can import the SafeCrawler class
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app import SafeCrawler
from document_history import DocumentHistory

# Configure page
st.set_page_config(
    page_title="Web Crawler & Documentation Manager",
    page_icon="🕸️",
    layout="wide"
)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

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

if "active_tab" not in st.session_state:
    st.session_state.active_tab = "crawler"

# Load the crawled content
def load_content():
    content_path = os.path.join("crawled_content", "content_store.json")
    
    try:
        with open(content_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        log_error(f"Error loading content: {e}")
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
    progress_text.text("Starting crawl...")
    
    # Function to update progress during crawling
    def progress_callback(current_url, links_crawled, total_links):
        progress = links_crawled / max(1, min(total_links, max_links))
        progress_bar.progress(progress)
        progress_text.text(f"{int(progress * 100)}% - Crawling: {current_url}")
    
    # Start crawling in a way that updates progress
    try:
        with st.spinner(f"Crawling {url}..."):
            # Perform the crawl with progress callback
            new_content_store = crawler.crawl(
                url, 
                max_depth=max_depth, 
                keyword=keyword, 
                max_links=max_links, 
                progress_callback=progress_callback
            )
            
            # Update progress to 100%
            progress_bar.progress(1.0)
            progress_text.text("100% - Crawl complete!")
            
            # Merge new content with existing content instead of replacing
            if 'content_store' in st.session_state and st.session_state.content_store:
                # Update existing content store with new content
                st.session_state.content_store.update(new_content_store)
                merged_content = st.session_state.content_store
            else:
                # If no existing content, just use the new content
                merged_content = new_content_store
                st.session_state.content_store = merged_content
            
            # Process document history
            st.session_state.doc_history.process_content_store(new_content_store)
            
            st.session_state.crawl_complete = True
            st.session_state.crawl_status = "complete"
            
            # Save the merged content to disk
            os.makedirs("crawled_content", exist_ok=True)
            with open(os.path.join("crawled_content", "content_store.json"), "w") as f:
                json.dump(merged_content, f)
                
            return merged_content
    except Exception as e:
        error_msg = f"Error during crawling: {str(e)}"
        log_error(error_msg)
        st.session_state.crawl_status = "error"
        return {}
    finally:
        # Remove progress elements after completion
        progress_placeholder.empty()
        progress_text.empty()

# Delete a specific document
def delete_document(url):
    """Delete a document from the content store and document history"""
    try:
        # Remove from content store
        if 'content_store' in st.session_state and url in st.session_state.content_store:
            del st.session_state.content_store[url]
            
            # Save updated content store
            with open(os.path.join("crawled_content", "content_store.json"), "w") as f:
                json.dump(st.session_state.content_store, f)
        
        return True
    except Exception as e:
        log_error(f"Error deleting document: {e}")
        return False

# Reset crawl data
def reset_crawl_data():
    """Reset crawl data while preserving document history"""
    try:
        # Clear content store
        st.session_state.content_store = {}
        
        # Clear crawl status
        st.session_state.crawl_status = None
        st.session_state.crawl_progress = 0
        st.session_state.crawl_complete = False
        
        # Delete content store file if exists
        content_path = os.path.join("crawled_content", "content_store.json")
        if os.path.exists(content_path):
            os.remove(content_path)
            
        return True
    except Exception as e:
        log_error(f"Error resetting crawl data: {e}")
        return False

# Clear all data
def clear_all_data():
    """Clear all data including document history"""
    try:
        # Reset crawl data
        reset_crawl_data()
        
        # Clear document history
        st.session_state.doc_history = DocumentHistory()
        
        # Clear chat history
        if "chat_messages" in st.session_state:
            st.session_state.chat_messages = []
        
        return True
    except Exception as e:
        log_error(f"Error clearing all data: {e}")
        return False

# Display crawler tab content
def show_crawler_tab():
    st.subheader("Crawler Configuration")
    
    # URL input
    url = st.text_input("Enter URL to crawl", "https://docs.snowflake.com/")
    
    # Crawler parameters in columns for better layout
    col1, col2 = st.columns(2)
    
    with col1:
        max_depth = st.slider("Maximum crawl depth", 1, 3, 2)
        keyword = st.text_input("Filter links by keyword (optional)")
    
    with col2:
        max_links = st.slider("Maximum links to crawl", 1, 20, 10)
    
    # Start crawling button
    if st.button("Start Crawling", type="primary", use_container_width=True):
        content_store = start_crawl(url, max_depth, keyword if keyword else None, max_links)
        if content_store:
            st.success(f"Crawling complete! Collected {len(content_store)} pages.")
    
    # Data management section
    st.markdown("---")
    st.subheader("Data Management")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Reset Crawl Data", type="secondary", help="Clear crawled content", use_container_width=True):
            reset_crawl_data()
            st.success("Crawl data reset successfully!")
            st.experimental_rerun()
    
    with col2:
        if st.button("Clear All Data", type="secondary", help="Clear all data including document history", use_container_width=True):
            clear_all_data()
            st.success("All data cleared successfully!")
            st.experimental_rerun()

# Display documents tab content
def show_documents_tab():
    st.subheader("Crawled Documents")
    
    # Display documents with proper formatting
    content_store = st.session_state.content_store
    if content_store:
        st.write(f"Total documents: {len(content_store)}")
        
        # Search filter
        search_term = st.text_input("Filter documents", "", placeholder="Enter keywords to filter")
        
        # Filter documents based on search term
        filtered_docs = {}
        if search_term:
            for url, data in content_store.items():
                if (search_term.lower() in url.lower() or 
                    search_term.lower() in data.get('title', '').lower()):
                    filtered_docs[url] = data
        else:
            filtered_docs = content_store
        
        # Display filtered documents
        for url, data in filtered_docs.items():
            # Create a card-like UI for each document
            st.markdown(f"### {data.get('title', 'Untitled')}")
            st.markdown(f"**URL:** {url}")
            
            # Use columns for better layout
            col1, col2 = st.columns([3, 1])
            
            with col1:
                # Show preview button
                if st.button("Show Content Preview", key=f"preview_{url}"):
                    st.text_area("Content", data.get('content', '')[:1000] + "...", height=200, disabled=True)
            
            with col2:
                # Delete button
                if st.button("Delete Document", key=f"delete_{url}"):
                    if delete_document(url):
                        st.success("Document deleted successfully!")
                        st.experimental_rerun()
                    else:
                        st.error("Failed to delete document.")
            
            st.markdown("---")
    else:
        st.info("No documents found. Start crawling to collect documents.")

# Display logs tab content
def show_logs_tab():
    st.subheader("Crawler Logs")
    
    # Display logs
    if 'error_log' in st.session_state and st.session_state.error_log:
        st.write(f"Total logs: {len(st.session_state.error_log)}")
        
        # Create a text area for all logs
        log_text = "\n".join(reversed(st.session_state.error_log))
        st.text_area("Logs", log_text, height=300)
        
        # Clear logs button
        if st.button("Clear Logs", use_container_width=True):
            st.session_state.error_log = []
            st.success("Logs cleared successfully!")
            st.experimental_rerun()
    else:
        st.info("No logs available.")

# Display chat interface
def show_chat_interface():
    st.header("Chat with Documents")
    st.write("Ask questions about the documents you've crawled, and get AI-powered answers.")
    
    # Initialize chat history
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    
    # Display chat history
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

def main():
    # Load saved content if exists
    if 'content_store' not in st.session_state or not st.session_state.content_store:
        content_store = load_content()
        if content_store:
            st.session_state.content_store = content_store
    
    # Main app UI
    st.title("🕸️ Web Crawler & Documentation Manager")
    st.markdown("---")

    # Create tabs for navigation
    tab_options = ["Crawler", "Documents", "Logs", "Chat"]
    selected_tab = st.radio("Navigation", tab_options, horizontal=True)
    st.session_state.active_tab = selected_tab.lower()
    
    st.markdown("---")
    
    # Display the selected tab content
    if st.session_state.active_tab == "crawler":
        show_crawler_tab()
    elif st.session_state.active_tab == "documents":
        show_documents_tab()
    elif st.session_state.active_tab == "logs":
        show_logs_tab()
    elif st.session_state.active_tab == "chat":
        show_chat_interface()
    
    # Chat input is placed outside of any container
    if st.session_state.active_tab == "chat":
        # Chat input
        if prompt := st.chat_input("Ask a question about the crawled content..."):
            # Add user message to chat history
            st.session_state.chat_messages.append({"role": "user", "content": prompt})
            
            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Display assistant response with a spinner while processing
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                with st.spinner("Searching documents..."):
                    if not st.session_state.content_store:
                        response = "No documents have been crawled yet. Please crawl some content first."
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
                                for _, title, content, _ in relevant_content[:3]:
                                    response += f"**{title}**\n{content[:300]}...\n\n"
                
                # Display the response
                message_placeholder.markdown(response)
                
            # Add assistant response to chat history
            st.session_state.chat_messages.append({"role": "assistant", "content": response})

# Run the main function
if __name__ == "__main__":
    main()