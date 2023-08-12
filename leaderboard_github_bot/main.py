import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dataclasses import dataclass
from pydantic import BaseModel
import httpx
import json
from typing import Union
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

origins = [
    "http://localhost:5173",
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class NewColumn(BaseModel):
    dataset: str
    column: str
    numerical: bool


class NewRow(BaseModel):
    dataset: str
    row: dict[str, Union[str, int, float]]


class ChangedRow(BaseModel):
    dataset: str
    row: dict[str, Union[str, int, float]]


class NewLeaderboard(BaseModel):
    dataset: str
    data: str


class PullRequest(BaseModel):
    newColumns: list[NewColumn]
    newRows: list[NewRow]
    changedRows: list[ChangedRow]
    newLeaderboards: list[NewLeaderboard]


GITHUB_API_URL = "https://api.github.com"
REPO_OWNER = "Artur-Galstyan"
REPO_NAME = "leaderboard"


@app.post("/make_pull_request")
async def make_pull_request(pull_request: PullRequest):
    issue_body = ""
    changes = {}
    for new_leaderboard in pull_request.newLeaderboards:
        if new_leaderboard.dataset not in changes:
            changes[new_leaderboard.dataset] = {
                "newColumns": [],
                "newRows": [],
                "changedRows": [],
                "newLeaderboard": [],
            }
        changes[new_leaderboard.dataset]["newLeaderboard"] = new_leaderboard
    for new_column in pull_request.newColumns:
        if new_column.dataset not in changes:
            changes[new_column.dataset] = {
                "newColumns": [],
                "newRows": [],
                "changedRows": [],
            }
        changes[new_column.dataset]["newColumns"].append(new_column)
    for new_row in pull_request.newRows:
        if new_row.dataset not in changes:
            changes[new_row.dataset] = {
                "newColumns": [],
                "newRows": [],
                "changedRows": [],
            }
        changes[new_row.dataset]["newRows"].append(new_row)
    for changed_row in pull_request.changedRows:
        if changed_row.dataset not in changes:
            changes[changed_row.dataset] = {
                "newColumns": [],
                "newRows": [],
                "changedRows": [],
            }
        changes[changed_row.dataset]["changedRows"].append(changed_row)

    for dataset, dataset_changes in changes.items():
        database, datasetname = dataset.split("/")
        req = httpx.get(
            f"https://raw.githubusercontent.com/Artur-Galstyan/leaderboard/main/{database}/{datasetname}.md"
        )
        response_text = req.text
        response_text = response_text.split("---\n")[-1]
        rows = response_text.split("\n")
        rows = [row for row in rows if row != ""]
        if (
            "newLeaderboard" in dataset_changes
            and dataset_changes["newLeaderboard"] != ""
        ):
            rows = dataset_changes["newLeaderboard"].data.split("\n")
            rows = [row for row in rows if row != ""]

        for new_column in dataset_changes["newColumns"]:
            column_name = new_column.column
            rows[0] += f" {column_name} |"
            rows[1] += ":---:|"
            for i in range(2, len(rows)):
                rows[i] += " - |"

        for new_row in dataset_changes["newRows"]:
            temp_row = "|"
            for key, value in new_row.row.items():
                if key != "id":
                    temp_row += f" {value} |"
            rows.append(temp_row)

        for changed_row in dataset_changes["changedRows"]:
            for i in range(2, len(rows)):
                if i - 2 == changed_row.row["id"]:
                    rows[i] = "|"
                    for key, value in changed_row.row.items():
                        if key != "id":
                            rows[i] += f" {value} |"

        issue_body += f"======== NEW CHANGES FOR {dataset} ========" + "\n"
        issue_body += "```\n"
        for i, row in enumerate(rows):
            issue_body += row + "\n"
        issue_body += "```\n\n"
        issue_body += "\n\n" + "============================================" + "\n\n\n"

    issue_body += "\n\n\n" + "======== RAW PULL REQUEST ========" + "\n"
    issue_body += json.dumps(pull_request.model_dump(), indent=4)
    issue_body += "\n\n\n" + "==================================" + "\n\n\n"
    print(issue_body)
    GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues"
    headers = {
        "Method": "POST",
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"Bearer {os.environ['GITHUB_ACCESS_TOKEN']}",
    }
    body = {
        "title": "New changes",
        "body": issue_body,
    }

    req = httpx.post(GITHUB_API_URL, headers=headers, json=body)
    response = req.json()

    return {"status": "success", "response": json.dumps(response)}


def dev():
    uvicorn.run(
        "leaderboard_github_bot.main:app", host="0.0.0.0", port=8000, reload=True
    )


def start():
    uvicorn.run("leaderboard_github_bot.main:app", host="0.0.0.0", port=8000)
