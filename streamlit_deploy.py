import os
import streamlit as st
import tempfile

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

from langchain_chroma import Chroma
os.environ['OPENAI_API_KEY'] = st.secrets['OPENAI_API_KEY']

import chromadb
chromadb.api.client.SharedSystemClient.clear_system_cache()

@st.cache_resource
def load_pdf(_file):
  with tempfile.NamedTemporaryFile(mode='wb', delete=False) as tmp_file:
    tmp_file.write(_file.getvalue())
    tmp_file_path = tmp_file.name
    loader = PyPDFLoader(file_path=tmp_file_path)
    pages = loader.load_and_split()

  return pages

@st.cache_resource
def create_vector_store(_docs):
  text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
  split_docs = text_splitter.split_documents(_docs)
  persist_directory = './chroma_db_test'
  vectorstore = Chroma.from_documents(
    split_docs,
    OpenAIEmbeddings(model='text-embedding-3-small'),
    persist_directory=persist_directory
  )
  return vectorstore

@st.cache_resource
def get_vector_store(_docs):
  persist_directory = './chroma_db_test'
  if os.path.exists(persist_directory):
    return Chroma(
      persist_directory=persist_directory,
      embedding_function=OpenAIEmbeddings(model='text-embedding-3-small')
    )
  else:
    return create_vector_store(_docs)
  
def format_docs(docs):
  return '\n\n'.join(doc.page_content for doc in docs)

@st.cache_resource
def chaining(_pages):
  vectorstore = get_vector_store(_pages)
  retriever = vectorstore.as_retriever()

  qa_system_prompt = """
  You are an assistant for question-answering tasks. \
  Use the following pieces of retrieved context to answer the question. \
  If you don't know the answer, just say that you don't know. \
  Keep the answer perfect. please use imogi with the answer. \
  Please answer in Korean and use respectful language. \
  {context}
  """

  qa_prompt = ChatPromptTemplate.from_messages(
    [
      ('system', qa_system_prompt),
      ('human', '{input}'),
    ]
  )

  llm = ChatOpenAI(model='gpt-4o-mini')
  rag_chain = (
    {'context': retriever | format_docs, 'input': RunnablePassthrough()}
    | qa_prompt
    | llm
    | StrOutputParser()
  )
  return rag_chain

st.header('헌법 Q&A 챗봇 💬')
uploaded_file = st.file_uploader('Upload a PDF', type=['pdf'])
if uploaded_file is not None:
  pages = load_pdf(uploaded_file)

  rag_chain = chaining(pages)

  if 'messages' not in st.session_state:
    st.session_state['messages'] = [{'role': 'assistant', 'content':'헌법에 대해 무엇이든 물어보세요!'}]

  for msg in st.session_state.messages:
    st.chat_message(msg['role']).write(msg['content'])

  if prompt_message := st.chat_input('질문을 입력해주세요 :'):
    st.chat_message('human').write(prompt_message)
    st.session_state.messages.append({'role':'user', 'content':prompt_message})
    with st.chat_message('ai'):
      with st.spinner('Thinking...'):
        response = rag_chain.invoke(prompt_message)
        st.session_state.messages.append({'role': 'assistant', 'content':response})
        st.write(response)





