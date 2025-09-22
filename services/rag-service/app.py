#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG System - RAG Service（Ollama専用・psycopg3対応）
Ollama専用、軽量モード切り替え可能な日本語RAGサービス
"""

import asyncio
import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 設定
DATABASE_URL = os.getenv("DATABASE_URL")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
USE_OLLAMA = os.getenv("USE_OLLAMA", "true").lower() == "true"
LIGHTWEIGHT_MODE = os.getenv("LIGHTWEIGHT_MODE", "false").lower() == "true"
LLM_MODEL = os.getenv("LLM_MODEL", "japanese-stablelm:3b-instruct")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "multilingual-e5-large")

# psycopg3対応のデータベース接続
if DATABASE_URL:
    # psycopg3を使用するためのURL変更
    if "postgresql://" in DATABASE_URL and "+psycopg" not in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://")

# create_engineでpsycopg3を明示的に指定
engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# FastAPI アプリ初期化
service_type = "ollama"
app = FastAPI(title=f"RAG Service ({service_type})", version="2.0.0")

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# データモデル
class QueryRequest(BaseModel):
    query: str
    max_chunks: Optional[int] = 5
    similarity_threshold: Optional[float] = 0.7

class SearchRequest(BaseModel):
    query: str
    max_chunks: Optional[int] = 5
    similarity_threshold: Optional[float] = 0.7

class QueryResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    metadata: Dict[str, Any]

class SearchResponse(BaseModel):
    results: List[Dict[str, Any]]
    total_count: int
    metadata: Dict[str, Any]

@dataclass
class SearchResult:
    chunk_id: int
    document_id: int
    filename: str
    content: str
    similarity: float

@app.get("/health")
async def health_check():
    """ヘルスチェックエンドポイント - モデル準備状況も含む"""
    try:
        # データベース接続テスト
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        logger.error(f"データベース接続エラー: {e}")
        db_status = "disconnected"
    
    # Ollamaモデルの準備状況確認
    llm_ready = await check_ollama_model_ready(LLM_MODEL)
    embedding_ready = await check_ollama_model_ready(EMBEDDING_MODEL)
    
    # 全体のサービス状況判定
    all_models_ready = llm_ready["ready"] and embedding_ready["ready"]
    service_status = "ready" if all_models_ready and db_status == "connected" else "not_ready"
    
    return {
        "status": service_status,
        "service": "rag-service",
        "mode": service_type,
        "models": {
            "llm": {
                "name": LLM_MODEL,
                "ready": llm_ready["ready"],
                "status": llm_ready["status"],
                "message": llm_ready["message"]
            },
            "embedding": {
                "name": EMBEDDING_MODEL,
                "ready": embedding_ready["ready"],
                "status": embedding_ready["status"],
                "message": embedding_ready["message"]
            }
        },
        "database": db_status,
        "all_ready": all_models_ready,
        "psycopg_version": "3.x",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/")
async def root():
    """ルートエンドポイント"""
    return {
        "message": "RAG Service - Ollama専用",
        "mode": service_type,
        "llm_model": LLM_MODEL,
        "embedding_model": EMBEDDING_MODEL,
        "version": "2.0.0",
        "docs": "/docs"
    }

async def get_embeddings_ollama(text: str) -> List[float]:
    """Ollamaで埋め込みベクトルを生成"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/embeddings",
                json={"model": EMBEDDING_MODEL, "prompt": text},
                timeout=30.0
            )
            if response.status_code == 200:
                result = response.json()
                return result.get("embedding", [])
            else:
                logger.error(f"Ollama埋め込み生成エラー: {response.status_code}")
                # フォールバック: ダミーベクトル
                return [0.0] * 1024
    except Exception as e:
        logger.error(f"Ollama接続エラー: {e}")
        # フォールバック: ダミーベクトル
        return [0.0] * 768

async def check_ollama_model_exists(model_name: str) -> bool:
    """Ollamaモデルの存在確認"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{OLLAMA_URL}/api/tags", timeout=10.0)
            if response.status_code == 200:
                models = response.json()
                available_models = [m["name"] for m in models.get("models", [])]
                return model_name in available_models
            return False
    except Exception as e:
        logger.error(f"モデル存在確認エラー: {e}")
        return False

async def check_ollama_model_ready(model_name: str) -> Dict[str, Any]:
    """Ollamaモデルの準備状況を詳細チェック"""
    try:
        async with httpx.AsyncClient() as client:
            # モデル一覧取得
            response = await client.get(f"{OLLAMA_URL}/api/tags", timeout=10.0)
            if response.status_code != 200:
                return {"ready": False, "status": "ollama_unavailable", "message": "Ollama接続不可"}
            
            models = response.json()
            available_models = [m["name"] for m in models.get("models", [])]
            
            # モデル名のマッチング（:latest タグも考慮）
            model_found = False
            matched_model = model_name
            
            for available_model in available_models:
                # 完全一致
                if model_name == available_model:
                    model_found = True
                    matched_model = available_model
                    break
                # :latest タグ付きでマッチ
                elif f"{model_name}:latest" == available_model:
                    model_found = True
                    matched_model = available_model
                    break
                # ベース名でマッチ（逆パターン）
                elif available_model.replace(":latest", "") == model_name:
                    model_found = True
                    matched_model = available_model
                    break
            
            if not model_found:
                return {"ready": False, "status": "model_not_found", "message": f"モデル '{model_name}' が見つかりません"}
            
            # モデルの実際のテスト実行（軽量テスト）
            test_response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": matched_model,
                    "prompt": "hi",
                    "stream": False,
                    "options": {
                        "num_predict": 1  # 1トークンのみ生成してテスト
                    }
                },
                timeout=15.0
            )
            
            if test_response.status_code == 200:
                result = test_response.json()
                if result.get("response") is not None and "error" not in result:
                    return {"ready": True, "status": "ready", "message": f"モデル '{matched_model}' 準備完了"}
                else:
                    error_msg = result.get("error", "不明なエラー")
                    return {"ready": False, "status": "model_error", "message": f"モデル '{matched_model}' エラー: {error_msg}"}
            else:
                return {"ready": False, "status": "model_loading", "message": f"モデル '{matched_model}' 読み込み中"}
                
    except Exception as e:
        logger.error(f"モデル準備状況確認エラー: {e}")
        return {"ready": False, "status": "error", "message": f"エラー: {str(e)}"}

def parse_llm_response_with_confidence(response: str) -> Optional[Dict[str, Any]]:
    """LLM応答から自信度を抽出し、閾値チェックを行う"""
    try:

        # 自信度の抽出
        confidence_match = re.search(r'自信度[：:]\s*(\d+)%?', response)
        if not confidence_match:
            # 自信度が明示されていない場合はデフォルト値
            confidence = 50
        else:
            confidence = int(confidence_match.group(1))
        
        # 自信度が閾値以下の場合は無回答
        if confidence < 80:
            return None
        
        # 回答部分の抽出
        answer_match = re.search(r'回答[：:]\s*(.*?)(?=根拠[：:]|$)', response, re.DOTALL)
        if answer_match:
            answer = answer_match.group(1).strip()
        else:
            answer = response
        
        # 根拠部分の抽出
        evidence_match = re.search(r'根拠[：:]\s*(.*?)$', response, re.DOTALL)
        evidence = evidence_match.group(1).strip() if evidence_match else ""
        
        # フォーマットされた応答を作成
        formatted_response = f"""**回答**
{answer}

**自信度**: {confidence}%

**根拠**: {evidence if evidence else '提供されたコンテキストに基づいています'}"""
        
        return {
            "confidence": confidence,
            "answer": answer,
            "evidence": evidence,
            "formatted_response": formatted_response
        }
        
    except Exception as e:
        logger.error(f"応答パースエラー: {e}")
        return None

async def generate_llm_response_ollama(query: str, context: str) -> str:
    """Ollamaで回答を生成"""
    try:
        prompt = f"""以下のコンテキストに基づいて質問に回答してください。

【重要な制約】
1. 自信度が80%以上の場合のみ回答してください
2. 正答には1点、誤答には-3点、無回答には0点が与えられます
3. コンテキストに明確な情報がない場合は「提供された情報では回答できません」と述べてください
4. 推測や一般知識での補完は避け、提供された情報のみを使用してください

【回答フォーマット】
自信度: [0-100%]
回答: [具体的な回答内容]
根拠: [コンテキストの該当箇所]

コンテキスト:
{context}

質問: {query}

回答:"""

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": LLM_MODEL,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=60.0
            )
            
            if response.status_code == 200:
                result = response.json()
                raw_response = result.get("response", "")
                
                # 自信度チェックと応答のフォーマット確認
                parsed_response = parse_llm_response_with_confidence(raw_response)
                
                if parsed_response:
                    logger.info(f"LLM応答生成成功 (自信度: {parsed_response.get('confidence', 'N/A')}%)")
                    return parsed_response.get("formatted_response", raw_response)
                else:
                    logger.warning("自信度が低いため無回答を選択")
                    return "提供された情報では確実な回答ができないため、回答を控えさせていただきます。"
            else:
                logger.error(f"Ollama回答生成エラー: {response.status_code}")
                return "申し訳ございませんが、回答を生成できませんでした。"
                
    except Exception as e:
        logger.error(f"Ollama接続エラー: {e}")
        return "申し訳ございませんが、回答を生成できませんでした。"

async def search_similar_chunks(query_embedding: List[float], max_chunks: int = 5, similarity_threshold: float = 0.7) -> List[SearchResult]:
    """類似チャンクを検索"""
    session = SessionLocal()
    try:
        # ベクトルを文字列形式に変換してPostgreSQLで適切に処理
        embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
        
        # SQLAlchemyのパラメータバインディングではなく、直接文字列補間を使用
        sql_query = f"""
            SELECT 
                dc.id as chunk_id,
                dc.document_id,
                d.filename,
                dc.content,
                1 - (dc.embedding <=> '{embedding_str}'::vector) as similarity
            FROM document_chunks dc
            JOIN documents d ON dc.document_id = d.id
            WHERE 1 - (dc.embedding <=> '{embedding_str}'::vector) > :similarity_threshold
            ORDER BY dc.embedding <=> '{embedding_str}'::vector
            LIMIT :max_chunks
        """
        
        result = session.execute(text(sql_query), {
            "similarity_threshold": similarity_threshold,
            "max_chunks": max_chunks
        })
        
        results = []
        for row in result:
            results.append(SearchResult(
                chunk_id=row.chunk_id,
                document_id=row.document_id,
                filename=row.filename,
                content=row.content,
                similarity=row.similarity
            ))
        
        return results
        
    except Exception as e:
        logger.error(f"類似検索エラー: {e}")
        return []
    finally:
        session.close()

@app.post("/search", response_model=SearchResponse)
async def search_documents(request: SearchRequest):
    """ドキュメント検索エンドポイント（回答生成なし）"""
    try:
        logger.info(f"検索クエリ受信: {request.query}")
        
        # 入力検証
        if not request.query or not request.query.strip():
            raise HTTPException(status_code=422, detail="クエリが空です")
        
        if len(request.query.strip()) < 2:
            raise HTTPException(status_code=422, detail="クエリは2文字以上で入力してください")
        
        # クエリの埋め込みベクトルを生成（Ollamaのみ）
        query_embedding = await get_embeddings_ollama(request.query.strip())
        
        if not query_embedding or all(x == 0.0 for x in query_embedding):
            raise HTTPException(status_code=500, detail="埋め込みベクトルの生成に失敗しました")
        
        # 類似チャンクを検索
        similar_chunks = await search_similar_chunks(
            query_embedding, 
            request.max_chunks, 
            request.similarity_threshold
        )
        
        # 結果をフォーマット
        results = []
        for chunk in similar_chunks:
            results.append({
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "filename": chunk.filename,
                "content": chunk.content[:500] + "..." if len(chunk.content) > 500 else chunk.content,
                "similarity": round(chunk.similarity, 4)
            })
        
        return SearchResponse(
            results=results,
            total_count=len(results),
            metadata={
                "query": request.query.strip(),
                "max_chunks": request.max_chunks,
                "similarity_threshold": request.similarity_threshold,
                "timestamp": datetime.now().isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"検索エラー: {e}")
        raise HTTPException(status_code=500, detail=f"検索処理中にエラーが発生しました: {str(e)}")

@app.post("/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    """ドキュメントに対してクエリを実行"""
    try:
        logger.info(f"クエリ受信: {request.query}")
        
        # 入力検証
        if not request.query or not request.query.strip():
            raise HTTPException(status_code=422, detail="クエリが空です")
        
        if len(request.query.strip()) < 2:
            raise HTTPException(status_code=422, detail="クエリは2文字以上で入力してください")
        
        # クエリの埋め込みベクトルを生成（Ollamaのみ）
        query_embedding = await get_embeddings_ollama(request.query.strip())
        
        if not query_embedding or all(x == 0.0 for x in query_embedding):
            raise HTTPException(status_code=500, detail="埋め込みベクトルの生成に失敗しました")
        
        # 類似チャンクを検索
        similar_chunks = await search_similar_chunks(
            query_embedding, 
            request.max_chunks, 
            request.similarity_threshold
        )
        
        if not similar_chunks:
            return QueryResponse(
                answer="関連するドキュメントが見つかりませんでした。",
                sources=[],
                metadata={
                    "mode": service_type,
                    "model": LLM_MODEL,
                    "chunks_found": 0
                }
            )
        
        # コンテキストを構築
        context = "\n\n".join([f"[{chunk.filename}]: {chunk.content}" for chunk in similar_chunks])
        
        # 回答を生成（Ollamaのみ）
        answer = await generate_llm_response_ollama(request.query, context)
        
        # ソース情報を構築
        sources = [
            {
                "filename": chunk.filename,
                "content": chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content,
                "similarity": round(chunk.similarity, 3)
            }
            for chunk in similar_chunks
        ]
        
        # 会話履歴を保存
        await save_conversation(request.query, answer, sources)
        
        return QueryResponse(
            answer=answer,
            sources=sources,
            metadata={
                "mode": service_type,
                "model": LLM_MODEL,
                "chunks_found": len(similar_chunks),
                "timestamp": datetime.now().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"クエリ処理エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def save_conversation(question: str, answer: str, sources: List[Dict]):
    """会話履歴を保存"""
    session = SessionLocal()
    try:
        session.execute(text("""
            INSERT INTO conversations (session_id, question, answer, source_chunks, metadata)
            VALUES (:session_id, :question, :answer, :source_chunks, :metadata)
        """), {
            "session_id": str(uuid.uuid4()),
            "question": question,
            "answer": answer,
            "source_chunks": json.dumps(sources, ensure_ascii=False),
            "metadata": json.dumps({
                "mode": service_type,
                "model": LLM_MODEL,
                "timestamp": datetime.now().isoformat()
            }, ensure_ascii=False)
        })
        session.commit()
    except Exception as e:
        logger.error(f"会話履歴保存エラー: {e}")
        session.rollback()
    finally:
        session.close()

@app.get("/stats")
async def get_stats():
    """システム統計情報"""
    session = SessionLocal()
    try:
        result = session.execute(text("SELECT * FROM document_stats"))
        row = result.fetchone()
        if row:
            stats = dict(row._mapping)
        else:
            stats = {}
        
        conversation_count = session.execute(text("SELECT COUNT(*) FROM conversations")).scalar()
        stats["total_conversations"] = conversation_count
        
        return {
            "stats": stats,
            "mode": service_type,
            "models": {
                "llm": LLM_MODEL,
                "embedding": EMBEDDING_MODEL
            }
        }
    except Exception as e:
        logger.error(f"統計取得エラー: {e}")
        return {"error": str(e)}
    finally:
        session.close()

if __name__ == "__main__":
    uvicorn.run(
        "app:app", 
        host="0.0.0.0", 
        port=8000,
        reload=False,
        log_level="info"
    )
