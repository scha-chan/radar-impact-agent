"""Contrato do grafo LangGraph do RADAR: AgentState e os modelos que o compoem.

Os modelos Pydantic descrevem o formato de cada peca de evidencia e da saida
final (`ImpactAnalysis`), replicando o schema documentado no PRD (secao 8).
`AgentState` e um TypedDict porque e o formato que o LangGraph espera para
estado compartilhado entre nodes; os campos individuais usam esses modelos
para validacao.
"""

from __future__ import annotations

import operator
import os
import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, Field

from src import config  # noqa: F401 - carrega .env como efeito colateral do import

# RF-06.5: orcamento de execucao — nenhuma execucao roda indefinidamente.
# Estourar qualquer um forca human_review_required=true e risk_level
# minimo MEDIUM (decide_autonomy, graph/nodes.py), nunca deixando o
# requisito passar como se tivesse sido totalmente analisado.
MAX_STEPS_DEFAULT = int(os.getenv("MAX_STEPS", "12"))
MAX_WALL_TIME_SECONDS = int(os.getenv("MAX_WALL_TIME_SECONDS", "60"))

# Card 47: quantas vezes o revisor pode pedir reanálise numa mesma sessão
# escalada antes de ter que aprovar ou rejeitar. Guardado na rota da API
# (`submit_approval`); o orçamento de passos (`MAX_STEPS`) é o backstop.
MAX_REVIEW_ROUNDS = int(os.getenv("MAX_REVIEW_ROUNDS", "3"))

# RF-09.5: versao fixa gravada no state na criacao da execucao — spans,
# logs e auditoria leem daqui, nao de uma constante global direto, para a
# versao registrada ser a que estava em vigor quando a execucao comecou
# mesmo que o processo seja atualizado com a execucao ja em andamento.
AGENT_VERSION = os.getenv("AGENT_VERSION", "0.1.0")
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "1")
POLICY_VERSION = os.getenv("POLICY_VERSION", "1")

FeatureType = Literal[
    "login",
    "cadastro",
    "formulario",
    "api",
    "upload",
    "dashboard",
    "listagem",
    "notificacao",
    "integracao",
    "outro",
]

SeverityLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
ProbabilityLevel = Literal["RARE", "POSSIBLE", "LIKELY", "ALMOST_CERTAIN"]
RiskLevelLiteral = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
EvidenceType = Literal["code", "rag", "history", "reviewer"]
ApprovalDecision = Literal["APPROVED", "REJECTED"]


class Requirement(BaseModel):
    """Requisito extraido do texto bruto (RF-02)."""

    text: str
    feature_type: FeatureType
    search_terms: list[str] = Field(default_factory=list)


class CodeMatch(BaseModel):
    """Um trecho de codigo encontrado por `search_code` (RF-03.1)."""

    file: str
    snippet: str
    line: int | None = None


class PatternChunk(BaseModel):
    """Um padrao de impacto recuperado do RAG por `retrieve_patterns` (RF-03.2)."""

    content: str
    source: str
    similarity: float


class HistoryEntry(BaseModel):
    """Um commit ou PR relacionado, retornado por `fetch_history` (RF-03.3)."""

    type: Literal["commit", "pr"]
    ref: str
    description: str


class EvidenceSource(BaseModel):
    """Origem rastreavel de uma afirmacao do parecer (RF-04.5)."""

    type: EvidenceType
    ref: str


class Impact(BaseModel):
    """Impacto classificado por area, com evidencia associada (RF-04.1)."""

    area: str
    description: str
    severity: SeverityLevel
    evidence: str


class Risk(BaseModel):
    """Risco enumerado com severidade, probabilidade e mitigacao (RF-04.2)."""

    description: str
    severity: SeverityLevel
    probability: ProbabilityLevel
    mitigation: str | None = None


class ImpactAnalysisResult(BaseModel):
    """Saida estruturada de `analyze_impact` (RF-04, card 44).

    O LLM so classifica impactos/riscos/dependencias/testes a partir da
    evidencia coletada — nunca calcula `risk_level` nem `confidence` (isso
    e `score_risk`, Python puro, RF-05.4). E um recorte de `ImpactAnalysis`
    (a saida final): so os quatro campos que o modelo produz, sem os campos
    de identificacao/decisao/timestamp que o grafo preenche depois.
    """

    impacts: list[Impact] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    recommended_tests: list[str] = Field(default_factory=list)


class ComposedReport(BaseModel):
    """Saida do LLM em `04-compose-report` (card 45).

    O modelo so redige texto — condensa o requisito numa linha e escreve o
    resumo executivo. Nao decide nem altera nenhum campo estruturado do
    `ImpactAnalysis` (risco, confianca, impactos, riscos): esses sao
    montados deterministicamente e renderizados a partir do objeto.
    """

    requirement_summary: str
    executive_summary: str


class ImpactAnalysis(BaseModel):
    """Saida principal do RADAR, publicada como comentario na Issue de origem."""

    session_id: str
    issue_number: int | None
    requirement_summary: str
    risk_level: RiskLevelLiteral
    confidence: int = Field(ge=0, le=100)
    human_review_required: bool
    impacts: list[Impact] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    recommended_tests: list[str] = Field(default_factory=list)
    evidence_sources: list[EvidenceSource] = Field(default_factory=list)
    # False quando o parecer escalou sem nenhum impacto/risco identificado
    # (evidencia insuficiente ou orcamento estourado, card 46): `risk_level`
    # foi elevado ao piso MEDIUM, mas nao e um risco medido — a UI e o
    # comentario mostram "nao avaliado" em vez do nivel.
    risk_assessed: bool = True
    generated_at: datetime


class AgentState(TypedDict):
    """Estado compartilhado do grafo — contrato entre todos os nodes (secao 8)."""

    # identificacao e rastreio
    session_id: str
    correlation_id: str
    issue_number: int | None

    # versionamento (RF-09.5) — atributo fixo propagado a log, span e auditoria
    agent_version: str
    prompt_version: str
    policy_version: str

    # orcamento de execucao (RF-06.5) — steps_taken usa operator.add porque
    # os tres nodes de evidencia rodam em paralelo (fan-out via Send) e cada
    # um contribui +1 (graph/build.py::count_step); sem o reducer de soma,
    # LangGraph rejeitaria a escrita concorrente na mesma chave (mesmo
    # motivo de evidence_sources/tools_failed, abaixo).
    steps_taken: Annotated[int, operator.add]
    max_steps: int
    started_at: datetime

    # entrada
    raw_requirement: str
    requirement: Requirement | None

    # controle de fluxo
    is_adversarial: bool
    adversarial_reason: str | None
    retries_left: int
    # card 47: contexto que o revisor forneceu ao pedir reanálise (uma
    # entrada por rodada, acumulado); `review_rounds` conta as rodadas;
    # `reanalysis_requested` diz a `route_after_approval` para voltar a
    # `analyze_impact` em vez de publicar/arquivar.
    reviewer_context: list[str]
    review_rounds: int
    reanalysis_requested: bool
    approval_expires_at: datetime | None

    # evidencia coletada (populada em paralelo)
    code_matches: list[CodeMatch]
    impact_patterns: list[PatternChunk]
    change_history: list[HistoryEntry]
    # Annotated com operator.add: os tres nodes de evidencia rodam em
    # paralelo (fan-out via Send) e cada um pode escrever aqui - sem reducer
    # de acumulacao, o LangGraph rejeita a escrita concorrente na mesma
    # chave. code_matches/impact_patterns/change_history nao precisam disso
    # porque cada um e escrito por exatamente um node.
    evidence_sources: Annotated[list[EvidenceSource], operator.add]
    # Mesmo motivo: search_codebase e fetch_history podem sinalizar falha em
    # paralelo. Consumido por score_risk (ConfidenceInputs.tools_failed_
    # with_fallback, secao 11 do PRD) - card 11.
    tools_failed: Annotated[list[str], operator.add]

    # analise
    impacts: list[Impact]
    risks: list[Risk]
    dependencies: list[str]
    recommended_tests: list[str]

    # decisao
    risk_level: RiskLevelLiteral | None
    # False quando escalou sem impacto/risco identificado (card 46) — ver
    # ImpactAnalysis.risk_assessed. Definido em decide_autonomy.
    risk_assessed: bool
    confidence: int | None
    human_review_required: bool
    approval_decision: ApprovalDecision | None

    # saida
    analysis: ImpactAnalysis | None
    published_comment_url: str | None


def create_initial_state(
    raw_requirement: str,
    *,
    issue_number: int | None = None,
    max_retries: int = 2,
    max_steps: int = MAX_STEPS_DEFAULT,
) -> AgentState:
    """Monta o estado inicial do grafo a partir de um requisito bruto.

    `session_id` e `correlation_id` compartilham o mesmo valor para permitir
    correlacionar logs, trilha de auditoria e trace de uma mesma execucao
    (secao 14 do PRD). `max_steps` e parametro (e nao so o default do
    ambiente) para os testes do orcamento de execucao (RF-06.5, card 35)
    forcarem o estouro sem depender de mocks lentos.
    """
    session_id = uuid.uuid4().hex[:8]
    return AgentState(
        session_id=session_id,
        correlation_id=session_id,
        issue_number=issue_number,
        agent_version=AGENT_VERSION,
        prompt_version=PROMPT_VERSION,
        policy_version=POLICY_VERSION,
        steps_taken=0,
        max_steps=max_steps,
        started_at=datetime.now(timezone.utc),
        raw_requirement=raw_requirement,
        requirement=None,
        is_adversarial=False,
        adversarial_reason=None,
        retries_left=max_retries,
        reviewer_context=[],
        review_rounds=0,
        reanalysis_requested=False,
        approval_expires_at=None,
        code_matches=[],
        impact_patterns=[],
        change_history=[],
        evidence_sources=[],
        tools_failed=[],
        impacts=[],
        risks=[],
        dependencies=[],
        recommended_tests=[],
        risk_level=None,
        risk_assessed=True,
        confidence=None,
        human_review_required=False,
        approval_decision=None,
        analysis=None,
        published_comment_url=None,
    )
