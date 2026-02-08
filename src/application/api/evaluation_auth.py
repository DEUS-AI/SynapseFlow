"""
Autenticación para endpoints de evaluación.

Este módulo proporciona middleware de autenticación para los endpoints
de test/evaluación. Estos endpoints solo están disponibles cuando
SYNAPSEFLOW_EVAL_MODE=true y requieren una API key de test separada.
"""

import os
import logging
from typing import Optional

from fastapi import HTTPException, Header, Depends
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)


# ========================================
# Configuration
# ========================================

def is_eval_mode_enabled() -> bool:
    """Verifica si el modo de evaluación está habilitado."""
    return os.getenv("SYNAPSEFLOW_EVAL_MODE", "false").lower() in ("true", "1", "yes")


def get_eval_api_key() -> Optional[str]:
    """Obtiene la API key de evaluación desde variables de entorno."""
    return os.getenv("SYNAPSEFLOW_EVAL_API_KEY")


# ========================================
# API Key Authentication
# ========================================

# Header scheme para la API key de evaluación
eval_api_key_header = APIKeyHeader(
    name="X-Eval-API-Key",
    auto_error=False,
    description="API key para endpoints de evaluación"
)


class EvalAPIKeyAuth:
    """
    Middleware de autenticación para endpoints de evaluación.

    Verifica que:
    1. El modo de evaluación esté habilitado (SYNAPSEFLOW_EVAL_MODE=true)
    2. La API key provista en el header X-Eval-API-Key sea correcta
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Inicializa el autenticador.

        Args:
            api_key: API key esperada. Si no se provee, se lee de SYNAPSEFLOW_EVAL_API_KEY
        """
        self.expected_key = api_key or get_eval_api_key()

    async def __call__(
        self,
        api_key: Optional[str] = Depends(eval_api_key_header)
    ) -> str:
        """
        Verifica la autenticación.

        Args:
            api_key: API key del header

        Returns:
            str: La API key validada

        Raises:
            HTTPException: Si la autenticación falla
        """
        # Verificar que eval mode esté habilitado
        if not is_eval_mode_enabled():
            logger.warning("Attempt to access eval endpoint with SYNAPSEFLOW_EVAL_MODE disabled")
            raise HTTPException(
                status_code=403,
                detail="Evaluation endpoints are disabled. Set SYNAPSEFLOW_EVAL_MODE=true to enable."
            )

        # Verificar que hay una API key configurada
        if not self.expected_key:
            logger.error("SYNAPSEFLOW_EVAL_API_KEY not configured")
            raise HTTPException(
                status_code=500,
                detail="Evaluation API key not configured on server"
            )

        # Verificar que se proveyó una API key
        if not api_key:
            raise HTTPException(
                status_code=401,
                detail="Missing X-Eval-API-Key header"
            )

        # Verificar que la API key es correcta
        if api_key != self.expected_key:
            logger.warning(f"Invalid eval API key attempt")
            raise HTTPException(
                status_code=403,
                detail="Invalid evaluation API key"
            )

        return api_key


# ========================================
# Dependency Functions
# ========================================

# Instancia singleton del autenticador
_auth_instance: Optional[EvalAPIKeyAuth] = None


def get_eval_auth() -> EvalAPIKeyAuth:
    """
    Factory function para obtener el autenticador de evaluación.

    Returns:
        EvalAPIKeyAuth: Instancia del autenticador

    Raises:
        RuntimeError: Si la API key no está configurada
    """
    global _auth_instance

    if _auth_instance is None:
        api_key = get_eval_api_key()
        if not api_key:
            logger.warning("SYNAPSEFLOW_EVAL_API_KEY not set, eval auth will fail")
        _auth_instance = EvalAPIKeyAuth(api_key)

    return _auth_instance


async def verify_eval_access(
    api_key: Optional[str] = Depends(eval_api_key_header)
) -> str:
    """
    Dependency function para verificar acceso a endpoints de evaluación.

    Uso:
        @router.get("/test/endpoint")
        async def my_endpoint(auth: str = Depends(verify_eval_access)):
            ...

    Args:
        api_key: API key del header

    Returns:
        str: API key validada
    """
    auth = get_eval_auth()
    return await auth(api_key)


# ========================================
# Decorators & Utilities
# ========================================

def require_eval_mode(func):
    """
    Decorador que verifica que el modo de evaluación esté habilitado.

    Uso:
        @require_eval_mode
        async def my_function():
            ...
    """
    async def wrapper(*args, **kwargs):
        if not is_eval_mode_enabled():
            raise RuntimeError("Evaluation mode is not enabled")
        return await func(*args, **kwargs)
    return wrapper


def check_eval_mode_or_raise():
    """
    Utility function que lanza excepción si eval mode no está habilitado.

    Raises:
        HTTPException: Si SYNAPSEFLOW_EVAL_MODE no está activo
    """
    if not is_eval_mode_enabled():
        raise HTTPException(
            status_code=403,
            detail="Evaluation mode is disabled"
        )
