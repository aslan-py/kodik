"""Typed failures emitted by the pipeline runner and orchestration layer."""


class PipelineError(RuntimeError):
    """Base class for an expected, serializable pipeline failure."""


class PipelinePreconditionError(PipelineError):
    """The requested stage cannot start because its required input is absent."""


class PipelineBusinessError(PipelineError):
    """The requested pipeline mode is not valid for the selected stage."""


class PipelineInfrastructureError(PipelineError):
    """A transient database, broker, or external integration failure."""
