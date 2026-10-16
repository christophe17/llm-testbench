"""Erreurs typées de la couche LLM.

Chaque erreur porte un drapeau ``retryable`` : c'est lui, et lui seul, que la politique de
retry consulte. Un code HTTP ne suffit pas à décider (un 400 n'est jamais réessayable, un
529 « surchargé » l'est toujours), et un provider peut échouer sans code du tout (coupure
réseau, délai dépassé).
"""

from llm_testbench.llm.governance import DataClass


class LLMError(Exception):
    """Base de toutes les erreurs de la couche LLM."""

    retryable: bool = False


class ProviderError(LLMError):
    """Échec côté provider : réponse HTTP non 2xx, réseau, délai."""

    def __init__(
        self,
        message: str,
        *,
        backend: str,
        status_code: int | None = None,
        retryable: bool = False,
        retry_after_s: float | None = None,
    ) -> None:
        super().__init__(message)
        self.backend = backend
        self.status_code = status_code
        self.retryable = retryable
        self.retry_after_s = retry_after_s


class RateLimitedError(ProviderError):
    """429 : trop de requêtes. Réessayable, en respectant ``retry_after_s`` s'il est donné."""

    def __init__(
        self,
        message: str,
        *,
        backend: str,
        status_code: int | None = 429,
        retry_after_s: float | None = None,
    ) -> None:
        super().__init__(
            message,
            backend=backend,
            status_code=status_code,
            retryable=True,
            retry_after_s=retry_after_s,
        )


class ProviderUnavailableError(ProviderError):
    """5xx, 529 « surchargé », ou connexion impossible. Réessayable."""

    def __init__(self, message: str, *, backend: str, status_code: int | None = None) -> None:
        super().__init__(message, backend=backend, status_code=status_code, retryable=True)


class ProviderTimeoutError(ProviderError):
    """Délai dépassé avant la réponse. Réessayable (le provider n'a peut-être rien reçu)."""

    def __init__(self, message: str, *, backend: str) -> None:
        super().__init__(message, backend=backend, status_code=None, retryable=True)


class InvalidRequestError(ProviderError):
    """4xx hors 429 : la requête est fausse, la rejouer ne changera rien."""

    def __init__(self, message: str, *, backend: str, status_code: int | None = None) -> None:
        super().__init__(message, backend=backend, status_code=status_code, retryable=False)


class MissingCredentialsError(LLMError):
    """Variable d'environnement de clé API absente pour un backend qu'on tente d'utiliser."""


class UnknownBackendError(LLMError):
    """Backend absent de ``config/llm_backends.toml``."""


class BackendDisabledError(LLMError):
    """Backend déclaré mais désactivé (``enabled = false``)."""


class GovernanceViolation(LLMError):
    """La politique de gouvernance refuse ce backend pour cette classe de données.

    Levée AVANT tout appel réseau. Jamais convertie en repli silencieux : si un repli
    existe, c'est l'appelant qui le décide, et il est tracé.
    """

    def __init__(self, *, data_class: DataClass, backend: str, reasons: tuple[str, ...]) -> None:
        detail = " ; ".join(reasons) if reasons else "aucune raison fournie"
        super().__init__(
            f"backend {backend!r} refusé pour la classe de données {data_class.value!r} : {detail}"
        )
        self.data_class = data_class
        self.backend = backend
        self.reasons = reasons


class BudgetExceededError(LLMError):
    """Budget de tokens dépassé, par requête ou sur la fenêtre glissante."""


class CircuitOpenError(LLMError):
    """Le circuit breaker du backend est ouvert : on échoue vite sans appeler le provider."""

    def __init__(self, *, backend: str, retry_in_s: float) -> None:
        super().__init__(
            f"circuit ouvert pour le backend {backend!r}, nouvel essai possible dans "
            f"{retry_in_s:.1f} s"
        )
        self.backend = backend
        self.retry_in_s = retry_in_s


class StructuredOutputError(LLMError):
    """Sortie structurée invalide après épuisement des tentatives de réparation."""

    def __init__(self, message: str, *, attempts: int, raw_text: str, last_error: str) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.raw_text = raw_text
        self.last_error = last_error


class PromptError(LLMError):
    """Prompt introuvable, en-tête invalide, ou rendu impossible (variable manquante)."""
