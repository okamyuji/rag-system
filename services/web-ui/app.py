#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG System - Web UI
Streamlitを使用したWebインターフェース
"""

import json
import os
import time
import uuid
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List

import plotly.express as px
import plotly.graph_objects as go
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

def main():
    """メイン関数"""
    st.title("🤖 RAG System - 日本語ドキュメント質問応答システム")
    
    # サイドバー
    with st.sidebar:
        st.header("📊 システム状態")
        
        # サービス健康状態チェック
        rag_health = ui.check_service_health(RAG_SERVICE_URL, "RAG Service")
        doc_health = ui.check_service_health(DOCUMENT_PROCESSOR_URL, "Document Processor")
        
        # RAG Service状態表示
        if rag_health["healthy"] and rag_health["all_ready"]:
            st.success("✅ RAG Service: 完全準備完了")
        elif rag_health["healthy"]:
            st.warning("⚠️ RAG Service: 接続OK、モデル準備中")
            # モデル詳細表示
            if "models" in rag_health:
                models = rag_health["models"]
                if "llm" in models:
                    llm_status = "✅" if models["llm"]["ready"] else "⏳"
                    st.text(f"  {llm_status} LLM: {models['llm']['name']}")
                    if not models["llm"]["ready"]:
                        st.text(f"    状態: {models['llm']['message']}")
                if "embedding" in models:
                    emb_status = "✅" if models["embedding"]["ready"] else "⏳"
                    st.text(f"  {emb_status} 埋め込み: {models['embedding']['name']}")
                    if not models["embedding"]["ready"]:
                        st.text(f"    状態: {models['embedding']['message']}")
        else:
            st.error("❌ RAG Service: 接続エラー")
            if "error" in rag_health:
                st.text(f"エラー: {rag_health['error']}")
            
        # Document Processor状態表示
        if doc_health["healthy"] and doc_health["all_ready"]:
            st.success("✅ Document Processor: 完全準備完了")
        elif doc_health["healthy"]:
            st.warning("⚠️ Document Processor: 接続OK、モデル準備中")
            # 埋め込みモデル詳細表示
            if "embedding_model" in doc_health:
                emb_model = doc_health["embedding_model"]
                emb_status = "✅" if emb_model.get("ready", False) else "⏳"
                st.text(f"  {emb_status} 埋め込み: {emb_model.get('name', 'N/A')}")
                if not emb_model.get("ready", False):
                    st.text(f"    状態: {emb_model.get('message', 'ダウンロード中')}")
        else:
            st.error("❌ Document Processor: 接続エラー")
            if "error" in doc_health:
                st.text(f"エラー: {doc_health['error']}")
        
        # 機能別利用可能状況
        st.divider()
        st.header("🎯 利用可能機能")
        
        embedding_ready = ui.check_embedding_ready()
        llm_ready = ui.check_llm_ready()
        
        # ドキュメントアップロード
        if embedding_ready:
            st.success("📤 ドキュメントアップロード: 利用可能")
        else:
            st.error("📤 ドキュメントアップロード: 利用不可")
            st.caption("埋め込みモデルの準備が必要です")
        
        # 検索機能
        if embedding_ready:
            st.success("🔍 ドキュメント検索: 利用可能")
        else:
            st.error("🔍 ドキュメント検索: 利用不可")
            st.caption("埋め込みモデルの準備が必要です")
            
        # 質問応答機能
        if llm_ready and embedding_ready:
            st.success("💬 質問応答: 利用可能")
        elif embedding_ready:
            st.warning("💬 質問応答: 部分利用可能")
            st.caption("LLMモデルが準備中のため、検索のみ利用可能")
        else:
            st.error("💬 質問応答: 利用不可")
            st.caption("両方のモデルの準備が必要です")
        
        st.divider()
        
        # セッション情報
        st.header("🔗 セッション情報")
        st.info(f"セッションID: {st.session_state.session_id[:8]}...")
        
        if st.button("🔄 新しいセッション開始"):
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.conversation_history = []
            st.rerun()
    
    # メインコンテンツ
    tab1, tab2, tab3, tab4 = st.tabs(["💬 質問応答", "📄 ドキュメント管理", "🔍 検索", "📊 統計"])
    
    # 質問応答タブ
    with tab1:
        show_chat_interface()
    
    # ドキュメント管理タブ
    with tab2:
        show_document_management()
    
    # 検索タブ
    with tab3:
        show_search_interface()
    
    # 統計タブ
    with tab4:
        show_statistics()

def show_chat_interface():
    """チャットインターフェースを表示"""
    st.header("💬 ドキュメントに質問する")
    
    # 会話履歴の表示
    conversation_container = st.container()
    
    with conversation_container:
        if st.session_state.conversation_history:
            for i, conv in enumerate(st.session_state.conversation_history):
                # ユーザーの質問
                with st.chat_message("user"):
                    st.write(conv["question"])
                
                # アシスタントの回答
                with st.chat_message("assistant"):
                    st.write(conv["answer"])
                    
                    # ソース情報
                    if conv.get("sources"):
                        with st.expander("📚 参照ソース"):
                            for j, source in enumerate(conv["sources"]):
                                st.write(f"**{j+1}. {source['filename']}** (類似度: {source['similarity']:.3f})")
                                st.write(f"```\n{source['content_preview']}\n```")
        
        # 新しい質問の入力
        question = st.chat_input("ドキュメントについて質問してください...")
        
        if question:
            # LLMモデル準備状況チェック（質問応答に必要）
            if not ui.check_llm_ready():
                st.error("⚠️ LLMモデルの準備が完了していません")
                st.info("サイドバーでLLMモデルの準備状況を確認してください。準備完了後に質問応答が可能になります。")
                
                # 埋め込みモデルが準備完了している場合は検索機能を案内
                if ui.check_embedding_ready():
                    st.info("💡 ドキュメント検索機能は利用可能です。「検索」タブをお試しください。")
                return
            
            # ユーザーの質問を表示
            with st.chat_message("user"):
                st.write(question)
            
            # 回答を生成
            with st.chat_message("assistant"):
                with st.spinner("回答を生成中..."):
                    result = ui.query_rag(question, st.session_state.session_id)
                
                if result["success"]:
                    data = result["data"]
                    answer = data["answer"]
                    sources = data["sources"]
                    
                    st.write(answer)
                    
                    # ソース情報
                    if sources:
                        with st.expander("📚 参照ソース"):
                            for i, source in enumerate(sources):
                                st.write(f"**{i+1}. {source['filename']}** (類似度: {source['similarity']:.3f})")
                                st.write(f"```\n{source['content_preview']}\n```")
                    
                    # 会話履歴に追加
                    st.session_state.conversation_history.append({
                        "question": question,
                        "answer": answer,
                        "sources": sources,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                else:
                    st.error(f"エラーが発生しました: {result['error']}")
            
            st.rerun()

def show_document_management():
    """ドキュメント管理インターフェースを表示"""
    st.header("📄 ドキュメント管理")
    
    # ファイルアップロード
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📤 ファイルアップロード")
        uploaded_file = st.file_uploader(
            "PDFまたはOfficeファイルを選択してください",
            type=["pdf", "docx", "pptx", "xlsx", "txt", "md"],
            help="対応形式: PDF, Word, PowerPoint, Excel, テキストファイル"
        )
        
        if uploaded_file is not None:
            # 埋め込みモデル準備状況チェック（ドキュメント処理に必要）
            if not ui.check_embedding_ready():
                st.warning("⚠️ 埋め込みモデルの準備が完了していません")
                st.info("サイドバーで埋め込みモデルの準備状況を確認してください。準備完了後にアップロードが可能になります。")
                st.button("アップロード", disabled=True)
            elif st.button("アップロード"):
                with st.spinner("ファイルをアップロード中..."):
                    result = ui.upload_document(uploaded_file)
                
                if result["success"]:
                    st.success(f"✅ ファイル '{uploaded_file.name}' がアップロードされました")
                    st.info("🔄 バックグラウンドで処理中です。しばらくお待ちください。")
                    time.sleep(2)  # 少し待ってから更新
                    st.rerun()
                else:
                    st.error(f"❌ アップロードエラー: {result['error']}")
    
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
    
    # ドキュメント一覧
    st.subheader("📋 ドキュメント一覧")
    
    documents = ui.get_documents()
    
    if documents:
        # ステータス別カウント（pandas不使用）
        status_counts = Counter(doc['status'] for doc in documents)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("総ドキュメント数", len(documents))
        with col2:
            st.metric("処理済み", status_counts.get('processed', 0))
        with col3:
            st.metric("処理中", status_counts.get('uploaded', 0))
        with col4:
            st.metric("エラー", status_counts.get('error', 0))
        
        # ドキュメントテーブル（pandas不使用）
        table_data = []
        for doc in documents:
            table_data.append({
                'ID': doc.get('id', ''),
                'ファイル名': doc.get('filename', ''),
                'ステータス': doc.get('status', ''),
                'サイズ(MB)': format_file_size(doc.get('file_size', 0)),
                'チャンク数': doc.get('total_chunks', 0) or 0,
                'アップロード時刻': format_datetime(doc.get('upload_time', ''))
            })
        
        # 行選択機能付きテーブル
        event = st.dataframe(
            table_data,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        # 選択された行に対するアクション
        if event.selection.rows:
            selected_idx = event.selection.rows[0]
            selected_doc = documents[selected_idx]
            
            st.subheader(f"📄 {selected_doc['filename']} の詳細")
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.write(f"**ステータス**: {selected_doc['status']}")
                st.write(f"**ファイルサイズ**: {format_file_size(selected_doc['file_size'])} MB")
                st.write(f"**チャンク数**: {selected_doc.get('total_chunks', 0)}")
                
                if selected_doc.get('content_preview'):
                    st.write("**内容プレビュー**:")
                    st.text_area("", selected_doc['content_preview'], height=100, disabled=True)
            
            with col2:
                if st.button("🗑️ 削除", key=f"delete_{selected_doc['id']}"):
                    if st.session_state.get(f"confirm_delete_{selected_doc['id']}", False):
                        if ui.delete_document(selected_doc['id']):
                            st.success("✅ ドキュメントが削除されました")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("❌ 削除に失敗しました")
                    else:
                        st.session_state[f"confirm_delete_{selected_doc['id']}"] = True
                        st.warning("⚠️ もう一度クリックして削除を確定してください")
                        st.rerun()
    else:
        st.info("📝 アップロードされたドキュメントはありません")

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
    """統計情報を表示"""
    st.header("📊 システム統計")
    
    stats = ui.get_system_stats()
    
    if stats:
        # ドキュメント統計
        if "documents" in stats and stats["documents"]:
            st.subheader("📄 ドキュメント統計")
            
            doc_stats = stats["documents"]
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("総ドキュメント数", doc_stats.get("total_documents", 0))
            with col2:
                st.metric("処理済み", doc_stats.get("processed_documents", 0))
            with col3:
                st.metric("エラー", doc_stats.get("error_documents", 0))
            with col4:
                st.metric("総チャンク数", doc_stats.get("total_chunks", 0))
            
            # ファイルサイズ
            total_size_mb = (doc_stats.get("total_file_size", 0) or 0) / 1024 / 1024
            st.metric("総ファイルサイズ", f"{total_size_mb:.2f} MB")
        
        st.divider()
        
        # 会話統計
        if "conversations" in stats:
            st.subheader("💬 会話統計")
            
            conv_stats = stats["conversations"]
            
            # 日別統計のグラフ（pandas不使用）
            if "daily_stats" in conv_stats and conv_stats["daily_stats"]:
                daily_data = conv_stats["daily_stats"]
                
                # データを整形（pandas不使用）
                dates = []
                counts = []
                for item in daily_data:
                    date_str = item.get('conversation_date', '')
                    if date_str:
                        try:
                            date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                            dates.append(date_obj.strftime('%Y-%m-%d'))
                            counts.append(item.get('daily_count', 0))
                        except:
                            continue
                
                if dates and counts:
                    fig = px.bar(
                        x=dates,
                        y=counts,
                        title="日別会話数",
                        labels={'x': '日付', 'y': '会話数'}
                    )
                    st.plotly_chart(fig, use_container_width=True)
            
            # 最近の質問
            if "recent_questions" in conv_stats and conv_stats["recent_questions"]:
                st.subheader("🔄 最近の質問")
                recent_questions = conv_stats["recent_questions"]
                
                for i, q in enumerate(recent_questions):
                    with st.expander(f"質問 {i+1}: {q['question'][:50]}..."):
                        st.write(f"**質問**: {q['question']}")
                        st.write(f"**時刻**: {q['created_at']}")
    else:
        st.warning("📊 統計情報を取得できませんでした")

if __name__ == "__main__":
    main()
