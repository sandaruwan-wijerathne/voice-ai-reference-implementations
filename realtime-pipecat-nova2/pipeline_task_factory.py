from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.audio.interruptions.min_words_interruption_strategy import MinWordsInterruptionStrategy
from pipecat.transports.base_transport import BaseTransport
from typing import Optional


def create_pipeline_task(
    transport: BaseTransport,
    user_aggregator,
    llm,
    assistant_aggregator,
    *,
    audio_in_sample_rate: Optional[int] = None,
    audio_out_sample_rate: Optional[int] = None,
    enable_metrics: bool = True,
    enable_usage_metrics: bool = True,
) -> PipelineTask:
    pipeline = Pipeline(
        [
            transport.input(),
            user_aggregator,
            llm,
            transport.output(),
            assistant_aggregator,
        ]
    )

    params_kwargs = {
        "enable_metrics": enable_metrics,
        "enable_usage_metrics": enable_usage_metrics,
        "allow_interruptions": True,
        "interruption_strategies": [MinWordsInterruptionStrategy(min_words=3)],
    }   
    if audio_in_sample_rate is not None:
        params_kwargs["audio_in_sample_rate"] = audio_in_sample_rate
    if audio_out_sample_rate is not None:
        params_kwargs["audio_out_sample_rate"] = audio_out_sample_rate

    return PipelineTask(pipeline, params=PipelineParams(**params_kwargs))
