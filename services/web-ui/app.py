#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG System - Web UI
Streamlitを使用したWebインターフェース
"""

import os
import time
import uuid
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List

import requests
import streamlit as st

# 設定
RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "http://rag-service:8000")
DOCUMENT_PROCESSOR_URL = os.getenv("DOCUMENT_PROCESSOR_URL", "http://document-processor:8001")

# Streamlit設定
st.set_page_config(
    page_title="RAG System",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# セッション状態の初期化
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = []

class RAGSystemUI:
    """RAGシステムのUI管理クラス"""
    
    def __init__(self):
        self.rag_url = RAG_SERVICE_URL
        self.doc_url = DOCUMENT_PROCESSOR_URL
    
    def check_service_health(self, service_url: str, service_name: str) -> Dict[str, Any]:
        """サービスの健康状態を詳細チェック"""
        try:
            response = requests.get(f"{service_url}/health", timeout=30)
            if response.status_code == 200:
                health_data = response.json()
                return {
                    "healthy": True,
                    "status": health_data.get("status", "unknown"),
                    "all_ready": health_data.get("all_ready", False),
                    "models": health_data.get("models", {}),
                    "embedding_model": health_data.get("embedding_model", {}),
                    "database": health_data.get("database", "unknown"),
                    "details": health_data
                }
            else:
                return {
                    "healthy": False,
                    "status": "unhealthy",
                    "all_ready": False,
                    "error": f"HTTP {response.status_code}"
                }
        except Exception as e:
            return {
                "healthy": False,
                "status": "connection_error",
                "all_ready": False,
                "error": str(e)
            }
    
    def check_all_models_ready(self) -> bool:
        """全モデルの準備状況をチェック"""
        rag_health = self.check_service_health(self.rag_url, "RAG Service")
        doc_health = self.check_service_health(self.doc_url, "Document Processor")
        return rag_health.get("all_ready", False) and doc_health.get("all_ready", False)
    
    def check_embedding_ready(self) -> bool:
        """埋め込みモデルの準備状況をチェック（ドキュメントアップロード用）"""
        doc_health = self.check_service_health(self.doc_url, "Document Processor")
        if not doc_health.get("healthy", False):
            return False
        
        embedding_model = doc_health.get("embedding_model", {})
        return embedding_model.get("ready", False)
    
    def check_llm_ready(self) -> bool:
        """LLMモデルの準備状況をチェック（質問応答用）"""
        rag_health = self.check_service_health(self.rag_url, "RAG Service")
        if not rag_health.get("healthy", False):
            return False
        
        models = rag_health.get("models", {})
        llm_model = models.get("llm", {})
        return llm_model.get("ready", False)
    
    def upload_document(self, uploaded_file) -> Dict[str, Any]:
        """ドキュメントをアップロード"""
        try:
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
            response = requests.post(f"{self.doc_url}/upload", files=files, timeout=60)
            
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": response.text}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_documents(self) -> List[Dict[str, Any]]:
        """ドキュメント一覧を取得"""
        try:
            response = requests.get(f"{self.doc_url}/documents", timeout=30)
            if response.status_code == 200:
                return response.json().get("documents", [])
            return []
        except Exception:
            return []
    
    def delete_document(self, document_id: int) -> bool:
        """ドキュメントを削除"""
        try:
            response = requests.delete(f"{self.doc_url}/documents/{document_id}", timeout=30)
            return response.status_code == 200
        except Exception:
            return False
    
    def search_documents(self, query: str, max_results: int = 10) -> Dict[str, Any]:
        """ドキュメントを検索"""
        try:
            data = {
                "query": query,
                "max_chunks": max_results,
                "similarity_threshold": 0.5
            }
            response = requests.post(f"{self.rag_url}/search", json=data, timeout=60)
            
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": response.text}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def query_rag(self, question: str, session_id: str) -> Dict[str, Any]:
        """RAGシステムに質問"""
        try:
            data = {
                "query": question,
                "max_chunks": 5,
                "similarity_threshold": 0.5
            }
            response = requests.post(f"{self.rag_url}/query", json=data, timeout=120)
            
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": response.text}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        """会話履歴を取得"""
        try:
            response = requests.get(f"{self.rag_url}/conversations/{session_id}", timeout=30)
            if response.status_code == 200:
                return response.json().get("conversations", [])
            return []
        except Exception:
            return []
    
    def get_system_stats(self) -> Dict[str, Any]:
        """システム統計を取得"""
        try:
            response = requests.get(f"{self.rag_url}/stats", timeout=30)
            if response.status_code == 200:
                return response.json()
            return {}
        except Exception:
            return {}

# UIインスタンス
ui = RAGSystemUI()

def format_datetime(dt_str: str) -> str:
    """日時文字列をフォーマット"""
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M')
    except:
        return dt_str

def format_file_size(size_bytes: int) -> str:
    """ファイルサイズをMB形式でフォーマット"""
    return f"{size_bytes / 1024 / 1024:.2f}"

def show_model_line(label: str, ready: bool, name: str, message: str):
    """モデルの準備状況を 1 行で表示する"""
    st.text(f"  {'✅' if ready else '⏳'} {label}: {name}")
    if not ready:
        st.text(f"    状態: {message}")


def show_rag_models(health: Dict[str, Any]):
    for key, label in (("llm", "LLM"), ("embedding", "埋め込み")):
        model = health.get("models", {}).get(key)
        if model:
            show_model_line(label, model["ready"], model["name"], model.get("message"))


def show_processor_models(health: Dict[str, Any]):
    model = health.get("embedding_model")
    if model:
        show_model_line("埋め込み", model.get("ready", False), model.get("name", "N/A"), model.get("message", "ダウンロード中"))


def show_service_health(label: str, health: Dict[str, Any], show_models):
    """サービスの状態を表示する。接続できてモデルが準備中なら、モデルごとの状況も出す"""
    if health["healthy"] and health["all_ready"]:
        st.success(f"✅ {label}: 完全準備完了")
    elif health["healthy"]:
        st.warning(f"⚠️ {label}: 接続OK、モデル準備中")
        show_models(health)
    else:
        st.error(f"❌ {label}: 接続エラー")
        if "error" in health:
            st.text(f"エラー: {health['error']}")


def show_feature(label: str, available: bool):
    if available:
        st.success(f"{label}: 利用可能")
    else:
        st.error(f"{label}: 利用不可")
        st.caption("埋め込みモデルの準備が必要です")


def show_qa_feature(llm_ready: bool, embedding_ready: bool):
    if llm_ready and embedding_ready:
        st.success("💬 質問応答: 利用可能")
    elif embedding_ready:
        st.warning("💬 質問応答: 部分利用可能")
        st.caption("LLMモデルが準備中のため、検索のみ利用可能")
    else:
        st.error("💬 質問応答: 利用不可")
        st.caption("両方のモデルの準備が必要です")


def show_sidebar():
    st.header("📊 システム状態")
    show_service_health("RAG Service", ui.check_service_health(RAG_SERVICE_URL, "RAG Service"), show_rag_models)
    show_service_health(
        "Document Processor",
        ui.check_service_health(DOCUMENT_PROCESSOR_URL, "Document Processor"),
        show_processor_models,
    )

    st.divider()
    st.header("🎯 利用可能機能")
    embedding_ready = ui.check_embedding_ready()
    llm_ready = ui.check_llm_ready()
    show_feature("📤 ドキュメントアップロード", embedding_ready)
    show_feature("🔍 ドキュメント検索", embedding_ready)
    show_qa_feature(llm_ready, embedding_ready)

    st.divider()
    st.header("🔗 セッション情報")
    st.info(f"セッションID: {st.session_state.session_id[:8]}...")
    if st.button("🔄 新しいセッション開始"):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.conversation_history = []
        st.rerun()


def main():
    """メイン関数"""
    st.title("🤖 RAG System - 日本語ドキュメント質問応答システム")
    with st.sidebar:
        show_sidebar()

    tab1, tab2, tab3, tab4 = st.tabs(["💬 質問応答", "📄 ドキュメント管理", "🔍 検索", "📊 統計"])
    with tab1:
        show_chat_interface()
    with tab2:
        show_document_management()
    with tab3:
        show_search_interface()
    with tab4:
        show_statistics()


def show_sources(sources: List[Dict[str, Any]]):
    """回答の出典を表示する。rag-service は本文の先頭を content で返す"""
    if not sources:
        return
    with st.expander("📚 参照ソース"):
        for i, source in enumerate(sources):
            st.write(f"**{i+1}. {source['filename']}** (類似度: {source['similarity']:.3f})")
            st.write(f"```\n{source['content']}\n```")


def answer_question(question: str):
    """質問を送り、回答と出典を表示して会話履歴に足す"""
    if not ui.check_llm_ready():
        st.error("⚠️ LLMモデルの準備が完了していません")
        st.info("サイドバーでLLMモデルの準備状況を確認してください。準備完了後に質問応答が可能になります。")
        if ui.check_embedding_ready():
            st.info("💡 ドキュメント検索機能は利用可能です。「検索」タブをお試しください。")
        return

    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        with st.spinner("回答を生成中..."):
            result = ui.query_rag(question, st.session_state.session_id)
        if not result["success"]:
            st.error(f"エラーが発生しました: {result['error']}")
            st.rerun()
        data = result["data"]
        st.write(data["answer"])
        show_sources(data["sources"])
        st.session_state.conversation_history.append({
            "question": question,
            "answer": data["answer"],
            "sources": data["sources"],
            "timestamp": datetime.now().isoformat()
        })
    st.rerun()


def show_chat_interface():
    """チャットインターフェースを表示"""
    st.header("💬 ドキュメントに質問する")
    with st.container():
        for conv in st.session_state.conversation_history:
            with st.chat_message("user"):
                st.write(conv["question"])
            with st.chat_message("assistant"):
                st.write(conv["answer"])
                show_sources(conv.get("sources"))

        question = st.chat_input("ドキュメントについて質問してください...")
        if question:
            answer_question(question)


def show_metrics(items):
    """(ラベル, 値) の並びを、横に並べた数字で表示する"""
    for col, (label, value) in zip(st.columns(len(items)), items):
        with col:
            st.metric(label, value)


def show_upload():
    st.subheader("📤 ファイルアップロード")
    uploaded_file = st.file_uploader(
        "PDFまたはOfficeファイルを選択してください",
        type=["pdf", "docx", "pptx", "xlsx", "txt", "md"],
        help="対応形式: PDF, Word, PowerPoint, Excel, テキストファイル"
    )
    if uploaded_file is None:
        return
    if not ui.check_embedding_ready():
        st.warning("⚠️ 埋め込みモデルの準備が完了していません")
        st.info("サイドバーで埋め込みモデルの準備状況を確認してください。準備完了後にアップロードが可能になります。")
        st.button("アップロード", disabled=True)
        return
    if not st.button("アップロード"):
        return
    with st.spinner("ファイルをアップロード中..."):
        result = ui.upload_document(uploaded_file)
    if result["success"]:
        st.success(f"✅ ファイル '{uploaded_file.name}' がアップロードされました")
        st.info("🔄 バックグラウンドで処理中です。しばらくお待ちください。")
        time.sleep(2)  # 少し待ってから更新
        st.rerun()
    else:
        st.error(f"❌ アップロードエラー: {result['error']}")


def delete_with_confirmation(doc_id):
    """1 回目の押下で確認を求め、2 回目で削除する"""
    key = f"confirm_delete_{doc_id}"
    if not st.session_state.get(key, False):
        st.session_state[key] = True
        st.warning("⚠️ もう一度クリックして削除を確定してください")
        st.rerun()
    if ui.delete_document(doc_id):
        st.success("✅ ドキュメントが削除されました")
        time.sleep(1)
        st.rerun()
    else:
        st.error("❌ 削除に失敗しました")


def show_document_detail(doc: Dict[str, Any]):
    st.subheader(f"📄 {doc['filename']} の詳細")
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write(f"**ステータス**: {doc['status']}")
        st.write(f"**ファイルサイズ**: {format_file_size(doc['file_size'])} MB")
        st.write(f"**チャンク数**: {doc.get('total_chunks', 0)}")
        if doc.get('content_preview'):
            st.write("**内容プレビュー**:")
            st.text_area("", doc['content_preview'], height=100, disabled=True)
    with col2:
        if st.button("🗑️ 削除", key=f"delete_{doc['id']}"):
            delete_with_confirmation(doc['id'])


def show_document_list():
    st.subheader("📋 ドキュメント一覧")
    documents = ui.get_documents()
    if not documents:
        st.info("📝 アップロードされたドキュメントはありません")
        return

    status_counts = Counter(doc['status'] for doc in documents)
    show_metrics([
        ("総ドキュメント数", len(documents)),
        ("処理済み", status_counts.get('processed', 0)),
        ("処理中", status_counts.get('uploaded', 0)),
        ("エラー", status_counts.get('error', 0)),
    ])
    table_data = [{
        'ID': doc.get('id', ''),
        'ファイル名': doc.get('filename', ''),
        'ステータス': doc.get('status', ''),
        'サイズ(MB)': format_file_size(doc.get('file_size', 0)),
        'チャンク数': doc.get('total_chunks', 0) or 0,
        'アップロード時刻': format_datetime(doc.get('upload_time', ''))
    } for doc in documents]
    event = st.dataframe(table_data, hide_index=True, on_select="rerun", selection_mode="single-row")
    if event.selection.rows:
        show_document_detail(documents[event.selection.rows[0]])


def show_document_management():
    """ドキュメント管理インターフェースを表示"""
    st.header("📄 ドキュメント管理")
    col1, col2 = st.columns([2, 1])
    with col1:
        show_upload()
    with col2:
        st.subheader("ℹ️ サポート形式")
        st.markdown("""
        - **PDF**: テキスト抽出
        - **Word**: .docx形式
        - **PowerPoint**: .pptx形式  
        - **Excel**: .xlsx形式
        - **テキスト**: .txt, .md形式
        
        **日本語文書対応済み**
        """)
    st.divider()
    show_document_list()

def show_search_interface():
    """検索インターフェースを表示"""
    st.header("🔍 ドキュメント検索")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        search_query = st.text_input("検索クエリを入力してください", placeholder="例: 売上データ、機械学習の手法、等")
    
    with col2:
        max_results = st.selectbox("最大結果数", [5, 10, 20, 50], index=1)
    
    if search_query:
        if st.button("🔍 検索実行"):
            with st.spinner("検索中..."):
                result = ui.search_documents(search_query, max_results)
            
            if result["success"]:
                data = result["data"]
                results = data["results"]
                
                st.success(f"✅ {len(results)} 件の結果が見つかりました")
                
                if results:
                    for i, item in enumerate(results):
                        with st.expander(f"📄 {item['filename']} (類似度: {item['similarity']:.3f})"):
                            st.write("**内容**:")
                            st.write(item['content'])
                            st.write(f"**ドキュメントID**: {item['document_id']}")
                            st.write(f"**チャンクID**: {item['chunk_id']}")
                else:
                    st.warning("🔍 検索クエリに一致する結果が見つかりませんでした")
                    
            else:
                st.error(f"❌ 検索エラー: {result['error']}")

def show_statistics():
    """統計情報を表示する。rag-service の /stats は {"stats": {...}} の平らな形で返す"""
    st.header("📊 システム統計")
    stats = ui.get_system_stats().get("stats")
    if not stats:
        st.warning("📊 統計情報を取得できませんでした")
        return

    st.subheader("📄 ドキュメント統計")
    show_metrics([
        ("総ドキュメント数", stats.get("total_documents", 0)),
        ("処理済み", stats.get("processed_documents", 0)),
        ("エラー", stats.get("error_documents", 0)),
        ("総チャンク数", stats.get("total_chunks", 0)),
    ])
    total_size_mb = (stats.get("total_file_size", 0) or 0) / 1024 / 1024
    st.metric("総ファイルサイズ", f"{total_size_mb:.2f} MB")
    st.divider()
    st.subheader("💬 会話統計")
    st.metric("総会話数", stats.get("total_conversations", 0))

if __name__ == "__main__":
    main()
