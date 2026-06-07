"""
title: n8n Workflow Manager
description: List, view, create, update, and activate/deactivate n8n workflows via the n8n API
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
        n8n_api_key: str = Field(
            default="",
            description="n8n API key (generate in n8n Settings → API)",
        )

    def __init__(self):
        self.valves = self.Valves()

    def _headers(self):
        return {
            "X-N8N-API-KEY": self.valves.n8n_api_key,
            "Content-Type": "application/json",
        }

    def list_workflows(self) -> str:
        """List all n8n workflows showing their ID, name, and whether they are active."""
        resp = requests.get(
            f"{self.valves.n8n_base_url}/api/v1/workflows",
            headers=self._headers(),
            timeout=30,
        )
        if resp.status_code != 200:
            return f"Error {resp.status_code}: {resp.text[:500]}"
        workflows = resp.json().get("data", [])
        lines = [
            f"- **{w['name']}** (id=`{w['id']}`, active={w['active']})"
            for w in workflows
        ]
        return "\n".join(lines) or "No workflows found"

    def get_workflow(self, workflow_id: str) -> str:
        """
        Get the full definition of a workflow including its nodes and connections.
        :param workflow_id: The n8n workflow ID
        :return: Workflow JSON
        """
        resp = requests.get(
            f"{self.valves.n8n_base_url}/api/v1/workflows/{workflow_id}",
            headers=self._headers(),
            timeout=30,
        )
        if resp.status_code != 200:
            return f"Error {resp.status_code}: {resp.text[:500]}"
        return json.dumps(resp.json(), indent=2)[:4000]

    def activate_workflow(self, workflow_id: str) -> str:
        """
        Activate a workflow so it responds to its triggers.
        :param workflow_id: The n8n workflow ID to activate
        """
        resp = requests.patch(
            f"{self.valves.n8n_base_url}/api/v1/workflows/{workflow_id}",
            headers=self._headers(),
            json={"active": True},
            timeout=30,
        )
        if resp.status_code == 200:
            return f"Workflow {workflow_id} activated successfully"
        return f"Error {resp.status_code}: {resp.text[:500]}"

    def deactivate_workflow(self, workflow_id: str) -> str:
        """
        Deactivate a workflow so it stops responding to triggers.
        :param workflow_id: The n8n workflow ID to deactivate
        """
        resp = requests.patch(
            f"{self.valves.n8n_base_url}/api/v1/workflows/{workflow_id}",
            headers=self._headers(),
            json={"active": False},
            timeout=30,
        )
        if resp.status_code == 200:
            return f"Workflow {workflow_id} deactivated successfully"
        return f"Error {resp.status_code}: {resp.text[:500]}"

    def create_workflow(self, name: str, workflow_json: str) -> str:
        """
        Create a new n8n workflow.
        :param name: Name for the new workflow
        :param workflow_json: JSON string containing "nodes" array and "connections" object
        :return: The created workflow ID
        """
        try:
            body = json.loads(workflow_json)
        except json.JSONDecodeError as e:
            return f"Invalid JSON: {e}"
        body["name"] = name
        resp = requests.post(
            f"{self.valves.n8n_base_url}/api/v1/workflows",
            headers=self._headers(),
            json=body,
            timeout=30,
        )
        if resp.status_code in (200, 201):
            wf = resp.json()
            return f"Created workflow '{wf.get('name')}' with id=`{wf.get('id')}`"
        return f"Error {resp.status_code}: {resp.text[:500]}"

    def update_workflow(self, workflow_id: str, workflow_json: str) -> str:
        """
        Update an existing workflow's nodes and connections.
        :param workflow_id: The n8n workflow ID to update
        :param workflow_json: Full workflow JSON with "nodes" and "connections"
        """
        try:
            body = json.loads(workflow_json)
        except json.JSONDecodeError as e:
            return f"Invalid JSON: {e}"
        resp = requests.put(
            f"{self.valves.n8n_base_url}/api/v1/workflows/{workflow_id}",
            headers=self._headers(),
            json=body,
            timeout=30,
        )
        if resp.status_code == 200:
            return f"Workflow {workflow_id} updated successfully"
        return f"Error {resp.status_code}: {resp.text[:500]}"

    def delete_workflow(self, workflow_id: str) -> str:
        """
        Delete a workflow permanently. This cannot be undone.
        :param workflow_id: The n8n workflow ID to delete
        """
        resp = requests.delete(
            f"{self.valves.n8n_base_url}/api/v1/workflows/{workflow_id}",
            headers=self._headers(),
            timeout=30,
        )
        if resp.status_code == 200:
            return f"Workflow {workflow_id} deleted"
        return f"Error {resp.status_code}: {resp.text[:500]}"
