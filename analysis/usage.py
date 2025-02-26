from __future__ import annotations

from typing import Iterable
from analysis.models.openhands import EvaluationOutput
from pydantic import BaseModel

class ResourceUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cache_reads: int = 0
    cache_writes: int = 0
    response_latency: float = 0.0

    def __add__(self, other: ResourceUsage) -> ResourceUsage:
        return ResourceUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            cache_reads=self.cache_reads + other.cache_reads,
            cache_writes=self.cache_writes + other.cache_writes,
            response_latency=self.response_latency + other.response_latency,
        )

def per_iteration_resource_usage(output: EvaluationOutput) -> Iterable[ResourceUsage]:
    """
    
    """
    for iteration, step in enumerate(output.history):
        try:
            response_id = step['tool_call_metadata']['model_response']['id']
            usage = step['tool_call_metadata']['model_response']['usage']
        except KeyError:
            continue

        # Prompt tokens
        try:
            prompt_tokens = usage['prompt_tokens']
        except KeyError:
            prompt_tokens = 0

        # Completion tokens
        try:
            completion_tokens = usage['completion_tokens']
        except KeyError:
            completion_tokens = 0

        # Cache reads
        try:
            cache_reads = usage['prompt_tokens_details']['cached_tokens']
        except KeyError:
            cache_reads = 0

        # Cache writes
        try:
            cache_writes = usage['cache_creation_input_tokens']
        except KeyError:
            cache_writes = 0

        # Response latency
        response_latency = 0
        for entry in output.metrics['response_latencies']:
            if entry['response_id'] == response_id:
                response_latency = entry['latency']
                break

        yield ResourceUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cache_reads=cache_reads,
            cache_writes=cache_writes,
            response_latency=response_latency,
        )


def total_resource_usage(output: EvaluationOutput) -> ResourceUsage:
    return sum(per_iteration_resource_usage(output), ResourceUsage())
