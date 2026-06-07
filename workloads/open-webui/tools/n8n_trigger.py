"""
title: n8n Workflow Trigger
description: Trigger n8n workflows via webhook endpoints
author: homelab
version: 0.1.0
"""

import requests
import json
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        n8n_base_url: str = Field(
            default="http://n8n.n8n.svc.cluster.local:5678",
            description="n8n internal base URL",
        )

    def __init__(self):
        self.valves = self.Valves()

    def trigger_workflow(self, webhook_path: str, data: str = "{}") -> str:
        """
        Trigger an n8n workflow via its webhook path. Use this to run automations.
        :param webhook_path: The webhook path configured in the n8n Webhook trigger node (e.g. "backup-gitea")
        :param data: Optional JSON string of data to send to the workflow (default: "{}")
        :return: The workflow execution response
        """
        url = f"{self.valves.n8n_base_url}/webhook/{webhook_path}"
        headers = {"Content-Type": "application/json"}
        try:
            payload = json.loads(data) if data else {}
            resp = requests.post(url, json=payload, headers=headers, timeout=120)
            return f"Status: {resp.status_code}\nResponse: {resp.text[:2000]}"
        except Exception as e:
            return f"Error triggering workflow: {str(e)}"
