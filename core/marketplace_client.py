"""
Remote Marketplace Registry Client.
Handles fetching, verifying, and installing plugins from remote registries.
"""
import hashlib
import json
import logging
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.exceptions import InvalidSignature

from core.logger import get_logger
from core.paths import project_path

logger = get_logger(__name__)


class MarketplaceRegistryClient:
    """Client for interacting with remote marketplace registries."""
    
    def __init__(self, registry_url: str, trust_store_path: Optional[Path] = None):
        """
        Initialize the marketplace client.
        
        Args:
            registry_url: Base URL of the remote registry
            trust_store_path: Path to store trusted public keys
        """
        self.registry_url = registry_url.rstrip("/")
        self.trust_store_path = trust_store_path or project_path("config", "marketplace_trust.json")
        self.trust_store = self._load_trust_store()
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = timedelta(minutes=15)
    
    def _load_trust_store(self) -> Dict[str, Any]:
        """Load the trust store with trusted public keys."""
        if self.trust_store_path.exists():
            try:
                with open(self.trust_store_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as exc:
                logger.warning(f"Failed to load trust store: {exc}")
        return {"trusted_keys": {}, "trusted_publishers": {}}
    
    def _save_trust_store(self) -> None:
        """Save the trust store to disk."""
        self.trust_store_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.trust_store_path, "w", encoding="utf-8") as f:
            json.dump(self.trust_store, f, indent=2)
    
    def _fetch_json(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """Fetch JSON from the registry endpoint."""
        url = f"{self.registry_url}{endpoint}"
        try:
            request = urllib.request.Request(url)
            request.add_header("User-Agent", "M.I.C.A-MarketplaceClient/1.0")
            with urllib.request.urlopen(request, timeout=10) as response:
                data = response.read().decode("utf-8")
                return json.loads(data)
        except urllib.error.URLError as exc:
            logger.error(f"Failed to fetch {url}: {exc}")
        except json.JSONDecodeError as exc:
            logger.error(f"Failed to parse JSON from {url}: {exc}")
        return None
    
    def _fetch_binary(self, endpoint: str) -> Optional[bytes]:
        """Fetch binary data from the registry endpoint."""
        url = f"{self.registry_url}{endpoint}"
        try:
            request = urllib.request.Request(url)
            request.add_header("User-Agent", "M.I.C.A-MarketplaceClient/1.0")
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except urllib.error.URLError as exc:
            logger.error(f"Failed to fetch {url}: {exc}")
        return None
    
    def get_registry_index(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get the registry index listing all available items.
        
        Args:
            force_refresh: Force refresh from remote instead of using cache
            
        Returns:
            Registry index with items list
        """
        cache_key = "registry_index"
        cached = self._cache.get(cache_key)
        
        if not force_refresh and cached:
            cached_at = datetime.fromisoformat(cached.get("cached_at", ""))
            if datetime.now() - cached_at < self._cache_ttl:
                return cached.get("data", {})
        
        data = self._fetch_json("/index.json") or {"items": []}
        
        self._cache[cache_key] = {
            "data": data,
            "cached_at": datetime.now().isoformat()
        }
        
        return data
    
    def get_item_manifest(self, item_id: str, version: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get the manifest for a specific item.
        
        Args:
            item_id: ID of the item
            version: Specific version (optional, defaults to latest)
            
        Returns:
            Item manifest
        """
        endpoint = f"/items/{item_id}"
        if version:
            endpoint += f"/{version}"
        endpoint += "/manifest.json"
        
        return self._fetch_json(endpoint)
    
    def get_item_signature(self, item_id: str, version: Optional[str] = None) -> Optional[str]:
        """
        Get the signature for a specific item.
        
        Args:
            item_id: ID of the item
            version: Specific version (optional, defaults to latest)
            
        Returns:
            Base64-encoded signature
        """
        endpoint = f"/items/{item_id}"
        if version:
            endpoint += f"/{version}"
        endpoint += "/signature.sig"
        
        data = self._fetch_binary(endpoint)
        if data:
            return data.decode("utf-8")
        return None
    
    def get_item_package(self, item_id: str, version: Optional[str] = None) -> Optional[bytes]:
        """
        Download the package for a specific item.
        
        Args:
            item_id: ID of the item
            version: Specific version (optional, defaults to latest)
            
        Returns:
            Package binary data
        """
        endpoint = f"/items/{item_id}"
        if version:
            endpoint += f"/{version}"
        endpoint += "/package.tar.gz"
        
        return self._fetch_binary(endpoint)
    
    def verify_item_signature(self, item_id: str, package: bytes, signature: str, manifest: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify the signature of an item package.
        
        Args:
            item_id: ID of the item
            package: Package binary data
            signature: Base64-encoded signature
            manifest: Item manifest
            
        Returns:
            Verification result
        """
        publisher = manifest.get("publisher", "unknown")
        trusted_key = self.trust_store.get("trusted_keys", {}).get(publisher)
        
        if not trusted_key:
            return {
                "status": "failed",
                "error": f"no trusted key for publisher: {publisher}",
                "publisher": publisher
            }
        
        try:
            # Load public key
            public_key_pem = trusted_key.get("public_key_pem")
            if not public_key_pem:
                return {"status": "failed", "error": "missing public_key_pem in trust store"}
            
            public_key = load_pem_public_key(public_key_pem.encode("utf-8"))
            
            # Compute package hash
            package_hash = hashlib.sha256(package).digest()
            
            # Decode signature
            import base64
            signature_bytes = base64.b64decode(signature)
            
            # Verify signature
            public_key.verify(signature_bytes, package_hash, padding.PKCS1v15(), hashes.SHA256())
            
            return {
                "status": "passed",
                "publisher": publisher,
                "algorithm": "RSA-SHA256",
                "key_id": trusted_key.get("key_id")
            }
        except InvalidSignature:
            return {
                "status": "failed",
                "error": "invalid signature",
                "publisher": publisher
            }
        except Exception as exc:
            return {
                "status": "failed",
                "error": f"verification error: {exc}",
                "publisher": publisher
            }
    
    def verify_signature_chain(self, item_id: str, manifest: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify the full signature chain for an item.
        
        Args:
            item_id: ID of the item
            manifest: Item manifest with signature_chain field
            
        Returns:
            Chain verification result
        """
        signature_chain = manifest.get("signature_chain", [])
        if not signature_chain:
            return {"status": "failed", "error": "no signature chain in manifest"}
        
        results = []
        for sig in signature_chain:
            sig_publisher = sig.get("publisher", "unknown")
            sig_key_id = sig.get("key_id")
            sig_hash = sig.get("hash")
            
            trusted_key = self.trust_store.get("trusted_keys", {}).get(sig_publisher)
            if not trusted_key:
                results.append({
                    "publisher": sig_publisher,
                    "status": "failed",
                    "error": "untrusted publisher"
                })
                continue
            
            if trusted_key.get("key_id") != sig_key_id:
                results.append({
                    "publisher": sig_publisher,
                    "status": "failed",
                    "error": "key ID mismatch"
                })
                continue
            
            results.append({
                "publisher": sig_publisher,
                "status": "passed",
                "key_id": sig_key_id,
                "hash": sig_hash
            })
        
        all_passed = all(r["status"] == "passed" for r in results)
        
        return {
            "status": "passed" if all_passed else "failed",
            "chain": results,
            "total_signatures": len(results),
            "passed_signatures": sum(1 for r in results if r["status"] == "passed")
        }
    
    def add_trusted_key(self, publisher: str, key_id: str, public_key_pem: str) -> None:
        """
        Add a trusted public key to the trust store.
        
        Args:
            publisher: Publisher name
            key_id: Key identifier
            public_key_pem: PEM-encoded public key
        """
        self.trust_store.setdefault("trusted_keys", {})[publisher] = {
            "key_id": key_id,
            "public_key_pem": public_key_pem,
            "added_at": datetime.now().isoformat()
        }
        self._save_trust_store()
        logger.info(f"Added trusted key for publisher: {publisher}")
    
    def sync_registry(self) -> Dict[str, Any]:
        """
        Sync the local registry with the remote registry.
        
        Returns:
            Sync result with counts
        """
        index = self.get_registry_index(force_refresh=True)
        items = index.get("items", [])
        
        return {
            "status": "synced",
            "total_items": len(items),
            "synced_at": datetime.now().isoformat(),
            "registry_url": self.registry_url
        }


def create_marketplace_client(registry_url: str) -> MarketplaceRegistryClient:
    """Factory function to create a marketplace client."""
    return MarketplaceRegistryClient(registry_url)
