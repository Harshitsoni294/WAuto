import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional
import uuid
import logging
from datetime import datetime
from config import settings as app_settings

logger = logging.getLogger(__name__)

class VectorService:
    def __init__(self):
        # Initialize ChromaDB with persistent storage
        self.client = chromadb.PersistentClient(
            path=app_settings.CHROMA_PERSIST_DIRECTORY,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Create or get collection for WhatsApp messages
        self.collection = self.client.get_or_create_collection(
            name="whatsapp_messages",
            metadata={"hnsw:space": "cosine"}
        )
    
    async def add_message(
        self, 
        contact_id: str, 
        text: str, 
        sender: str, 
        receiver: str, 
        timestamp: Optional[int] = None,
        embedding: Optional[List[float]] = None
    ) -> str:
        """Add a message to the vector store"""
        try:
            message_id = str(uuid.uuid4())
            ts = timestamp if timestamp else int(datetime.now().timestamp() * 1000)
            
            # If no embedding provided, we'll let ChromaDB handle it
            # In production, you'd want to use the Gemini embedding service
            
            metadata = {
                "contact_id": contact_id,
                "sender": sender,
                "receiver": receiver,
                "timestamp": ts,
                "datetime": datetime.fromtimestamp(ts / 1000).isoformat()
            }
            
            if embedding:
                self.collection.add(
                    ids=[message_id],
                    documents=[text],
                    embeddings=[embedding],
                    metadatas=[metadata]
                )
            else:
                self.collection.add(
                    ids=[message_id],
                    documents=[text],
                    metadatas=[metadata]
                )
            
            logger.info(f"Added message to vector store: {message_id}")
            return message_id
            
        except Exception as e:
            logger.error(f"Error adding message to vector store: {e}")
            raise Exception(f"Failed to add message: {str(e)}")
    
    async def get_conversation_history(
        self, 
        contact_id: str, 
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get conversation history for a contact"""
        try:
            results = self.collection.get(
                where={"contact_id": contact_id},
                include=["documents", "metadatas"]
            )
            
            # Sort by timestamp
            messages = []
            for i, doc in enumerate(results["documents"]):
                metadata = results["metadatas"][i]
                messages.append({
                    "text": doc,
                    "sender": metadata["sender"],
                    "receiver": metadata["receiver"],
                    "timestamp": metadata["timestamp"],
                    "datetime": metadata["datetime"]
                })
            
            # Sort by timestamp and limit
            messages.sort(key=lambda x: x["timestamp"])
            return messages[-limit:] if limit else messages
            
        except Exception as e:
            logger.error(f"Error retrieving conversation history: {e}")
            return []
    
    async def search_similar_messages(
        self, 
        query_text: str, 
        contact_id: Optional[str] = None,
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for similar messages using semantic search"""
        try:
            where_filter = {"contact_id": contact_id} if contact_id else None
            
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results,
                where=where_filter,
                include=["documents", "metadatas", "distances"]
            )
            
            similar_messages = []
            for i, doc in enumerate(results["documents"][0]):
                metadata = results["metadatas"][0][i]
                distance = results["distances"][0][i]
                
                similar_messages.append({
                    "text": doc,
                    "sender": metadata["sender"],
                    "receiver": metadata["receiver"],
                    "timestamp": metadata["timestamp"],
                    "datetime": metadata["datetime"],
                    "similarity_score": 1 - distance  # Convert distance to similarity
                })
            
            return similar_messages
            
        except Exception as e:
            logger.error(f"Error searching similar messages: {e}")
            return []
    
    async def get_all_contacts(self) -> List[str]:
        """Get list of all contact IDs in the database"""
        try:
            results = self.collection.get(include=["metadatas"])
            contact_ids = set()
            
            for metadata in results["metadatas"]:
                contact_ids.add(metadata["contact_id"])
            
            return list(contact_ids)
            
        except Exception as e:
            logger.error(f"Error getting all contacts: {e}")
            return []
    
    async def delete_conversation(self, contact_id: str) -> bool:
        """Delete all messages for a contact"""
        try:
            results = self.collection.get(
                where={"contact_id": contact_id},
                include=["documents"]
            )
            
            if results["ids"]:
                self.collection.delete(ids=results["ids"])
                logger.info(f"Deleted conversation for contact: {contact_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error deleting conversation: {e}")
            return False

# Global instance
vector_service = VectorService()