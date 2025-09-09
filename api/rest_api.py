"""
REST API Server for Hallucination Risk Assessment
===============================================

Provides a JSON API endpoint to evaluate prompts for hallucination risk
using the EDFL/B2T/ISR framework.

Endpoints:
- POST /api/evaluate - Evaluate a prompt for hallucination risk
- GET /api/health - Health check

Usage:
    python api/rest_api.py --port 5000

Example request:
    curl -X POST http://localhost:5000/api/evaluate \
      -H "Content-Type: application/json" \
      -d '{
        "prompt": "Who won the 2019 Nobel Prize in Physics?",
        "settings": {
          "model": "gpt-4o-mini",
          "h_star": 0.05,
          "n_samples": 7
        }
      }'
"""

from __future__ import annotations

import json
import os
import traceback
from dataclasses import asdict
from typing import Any, Dict, Optional

from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

import sys
import os

# Load environment variables from .env file
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scripts.hallucination_toolkit import (
    OpenAIBackend,
    OpenAIItem,
    OpenAIPlanner,
    generate_answer_if_allowed,
    make_sla_certificate,
)


app = Flask(__name__)
CORS(app)  # Enable CORS for all origins


# Default settings
DEFAULT_SETTINGS = {
    "model": "gpt-4.1-mini",
    "n_samples": 7,
    "m": 6,
    "skeleton_policy": "closed_book",
    "temperature": 0.3,
    "h_star": 0.05,
    "isr_threshold": 1.0,
    "margin_extra_bits": 0.2,
    "B_clip": 12.0,
    "clip_mode": "one-sided",
    "generate_answer": False,
    # GPT-5 specific parameters
    "verbosity": "low",
    "reasoning_effort": "minimal",
}


def validate_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize settings with defaults."""
    validated = DEFAULT_SETTINGS.copy()
    validated.update(settings)

    # Type validation and constraints
    validated["n_samples"] = max(1, min(int(validated["n_samples"]), 15))
    validated["m"] = max(2, min(int(validated["m"]), 12))
    validated["temperature"] = max(0.0, min(float(validated["temperature"]), 1.0))
    validated["h_star"] = max(0.001, min(float(validated["h_star"]), 0.5))
    validated["isr_threshold"] = max(0.1, min(float(validated["isr_threshold"]), 5.0))
    validated["margin_extra_bits"] = max(0.0, min(float(validated["margin_extra_bits"]), 5.0))
    validated["B_clip"] = max(1.0, min(float(validated["B_clip"]), 50.0))

    if validated["skeleton_policy"] not in ["auto", "evidence_erase", "closed_book"]:
        validated["skeleton_policy"] = "closed_book"

    if validated["clip_mode"] not in ["one-sided", "symmetric"]:
        validated["clip_mode"] = "one-sided"

    # Validate GPT-5 specific parameters
    if validated["verbosity"] not in ["low", "medium", "high"]:
        validated["verbosity"] = "low"

    if validated["reasoning_effort"] not in ["minimal", "low", "medium", "high"]:
        validated["reasoning_effort"] = "minimal"

    return validated


@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "hallucination-risk-api",
        "version": "1.0.0"
    })


@app.route("/api/evaluate", methods=["POST"])
def evaluate_prompt():
    """
    Evaluate a prompt for hallucination risk.

    Request body:
    {
        "prompt": "Your question here",
        "api_key": "sk-...",  // Optional if OPENAI_API_KEY is set
        "settings": {
            "model": "gpt-4.1-mini",
            "h_star": 0.05,
            "n_samples": 7,
            "m": 6,
            "skeleton_policy": "closed_book",
            "temperature": 0.3,
            "isr_threshold": 1.0,
            "margin_extra_bits": 0.2,
            "B_clip": 12.0,
            "clip_mode": "one-sided",
            "generate_answer": false
        }
    }

    Response:
    {
        "success": true,
        "result": {
            "decision": "ANSWER" | "REFUSE",
            "decision_answer": true | false,
            "rationale": "Human-readable explanation",
            "metrics": {
                "delta_bar": 2.5,
                "b2t": 1.8,
                "isr": 1.39,
                "roh_bound": 0.023,
                "q_conservative": 0.1,
                "q_avg": 0.15
            },
            "answer": "Generated answer if requested and allowed",
            "sla_certificate": {...}
        },
        "settings_used": {...}
    }
    """
    try:
        # Parse request
        data = request.get_json()
        if not data:
            return jsonify({
                "success": false,
                "error": "Request body must be JSON"
            }), 400

        prompt = data.get("prompt", "").strip()
        if not prompt:
            return jsonify({
                "success": false,
                "error": "Prompt is required and cannot be empty"
            }), 400

        # Get API key
        api_key = data.get("api_key") or os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            return jsonify({
                "success": false,
                "error": "OpenAI API key is required. Provide it in request body or set OPENAI_API_KEY environment variable."
            }), 400

        # Validate settings
        settings = validate_settings(data.get("settings", {}))

        # Set API key in environment for OpenAI backend
        os.environ["OPENAI_API_KEY"] = api_key

        # Create evaluation item
        item = OpenAIItem(
            prompt=prompt,
            n_samples=settings["n_samples"],
            m=settings["m"],
            skeleton_policy=settings["skeleton_policy"],
        )

        # Initialize backend and planner
        backend = OpenAIBackend(model=settings["model"])
        # Store GPT-5 specific parameters in backend for later use
        backend.verbosity = settings["verbosity"]
        backend.reasoning_effort = settings["reasoning_effort"]

        planner = OpenAIPlanner(
            backend=backend,
            temperature=settings["temperature"],
        )

        # Run evaluation
        metrics = planner.run(
            [item],
            h_star=settings["h_star"],
            isr_threshold=settings["isr_threshold"],
            margin_extra_bits=settings["margin_extra_bits"],
            B_clip=settings["B_clip"],
            clip_mode=settings["clip_mode"],
        )

        metric = metrics[0]

        # Build response
        result = {
            "decision": "ANSWER" if metric.decision_answer else "REFUSE",
            "decision_answer": metric.decision_answer,
            "rationale": metric.rationale,
            "metrics": {
                "delta_bar": metric.delta_bar,
                "b2t": metric.b2t,
                "isr": metric.isr,
                "roh_bound": metric.roh_bound,
                "q_conservative": metric.q_conservative,
                "q_avg": metric.q_avg,
            },
        }

        # Generate answer if requested and allowed
        if settings["generate_answer"]:
            if metric.decision_answer:
                try:
                    answer = generate_answer_if_allowed(backend, item, metric, max_tokens_answer=256)
                    result["answer"] = answer if answer else "No answer generated"
                except Exception as e:
                    result["answer"] = f"Error generating answer: {str(e)}"
            else:
                result["answer"] = "Request refused - insufficient information confidence"

        # Generate SLA certificate
        try:
            report = planner.aggregate(
                [item], metrics,
                h_star=settings["h_star"],
                isr_threshold=settings["isr_threshold"],
                margin_extra_bits=settings["margin_extra_bits"]
            )
            cert = make_sla_certificate(report, model_name=settings["model"], confidence_1_minus_alpha=0.95)
            result["sla_certificate"] = asdict(cert)
        except Exception as e:
            result["sla_certificate"] = {"error": f"Failed to generate certificate: {str(e)}"}

        return jsonify({
            "success": True,
            "result": result,
            "settings_used": settings
        })

    except Exception as e:
        error_details = {
            "success": False,
            "error": str(e),
            "type": type(e).__name__,
        }

        # Include traceback in development
        if app.debug:
            error_details["traceback"] = traceback.format_exc()

        return jsonify(error_details), 500


@app.route("/api/models", methods=["GET"])
def list_models():
    """List supported OpenAI models."""
    return jsonify({
        "success": True,
        "models": [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4.1",
            "gpt-4.1-mini",
            "gpt-4.1-nano",
            "gpt-5",
            "gpt-5-mini",
            "gpt-5-nano"
        ],
        "recommended": "gpt-4.1-mini"
    })


@app.route("/api/settings/defaults", methods=["GET"])
def get_default_settings():
    """Get default evaluation settings."""
    return jsonify({
        "success": True,
        "defaults": DEFAULT_SETTINGS
    })


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "success": False,
        "error": "Endpoint not found"
    }), 404


@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        "success": False,
        "error": "Method not allowed"
    }), 405


def main():
    """Run the API server."""
    import argparse

    # Get defaults from environment variables
    default_host = os.getenv("API_HOST", "127.0.0.1")
    default_port = int(os.getenv("API_PORT", "3169"))
    default_debug = os.getenv("API_DEBUG", "false").lower() == "true"

    parser = argparse.ArgumentParser(description="Hallucination Risk API Server")
    parser.add_argument("--host", default=default_host, help=f"Host to bind to (default: {default_host})")
    parser.add_argument("--port", type=int, default=default_port, help=f"Port to bind to (default: {default_port})")
    parser.add_argument("--debug", action="store_true", default=default_debug, help="Enable debug mode")

    args = parser.parse_args()

    print(f"Starting Hallucination Risk API on {args.host}:{args.port}")
    if args.debug:
        print("Debug mode enabled")

    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug
    )


if __name__ == "__main__":
    main()

# Copyright (c) 2024 Hassana Labs
# Licensed under the MIT License - see LICENSE file for details
