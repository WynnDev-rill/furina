const DEFAULT_REPO = "WynnDev-rill/furina";
const DEFAULT_STATE_ISSUE = 42;

function parseState(body) {
  const match = String(body || "").match(/<!--\s*FURINA_LAB_STATE\s*([\s\S]*?)\s*FURINA_LAB_STATE\s*-->/);
  if (!match) return null;
  try {
    return JSON.parse(match[1]);
  } catch {
    return null;
  }
}

async function github(path, token) {
  const response = await fetch(`https://api.github.com${path}`, {
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "furina-lab"
    }
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`GitHub ${response.status}: ${text.slice(0, 180)}`);
  }
  return response.json();
}

function fallbackState() {
  return {
    cycleId: "dashboard-fallback",
    status: "blocked",
    currentPriority: "Connect GITHUB_TOKEN in the Furina Lab Vercel project",
    updatedAt: new Date().toISOString(),
    agents: {
      director: { status: "waiting", task: "Waiting for GitHub connection" },
      researcher: { status: "idle", task: "Behavioral benchmark ready" },
      engineer: { status: "idle", task: "Engineering OS installed" },
      reviewer: { status: "idle", task: "Waiting for a PR" },
      performance: { status: "idle", task: "Baseline ready" },
      ux: { status: "idle", task: "Waiting for UX audit cycle" }
    },
    metrics: { architecture: 8, persona: 6, memory: 6.5, learning: 5, agency: 3.5, localLatency: 7, ux: 7 },
    events: [{ at: "setup", actor: "System", message: "Dashboard is running in local fallback mode." }]
  };
}

module.exports = async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store, max-age=0");
  const token = process.env.GITHUB_TOKEN;
  const repo = process.env.FURINA_REPO || DEFAULT_REPO;
  const issueNumber = Number(process.env.FURINA_STATE_ISSUE || DEFAULT_STATE_ISSUE);

  if (!token) {
    return res.status(200).json({ configured: false, state: fallbackState(), pullRequests: [], commits: [], workflows: [] });
  }

  try {
    const encodedRepo = repo.split("/").map(encodeURIComponent).join("/");
    const [issue, pulls, commits, runs] = await Promise.all([
      github(`/repos/${encodedRepo}/issues/${issueNumber}`, token),
      github(`/repos/${encodedRepo}/pulls?state=open&per_page=8`, token),
      github(`/repos/${encodedRepo}/commits?per_page=8`, token),
      github(`/repos/${encodedRepo}/actions/runs?per_page=10`, token)
    ]);

    const state = parseState(issue.body) || fallbackState();
    const pullRequests = pulls.map((pr) => ({
      number: pr.number,
      title: pr.title,
      draft: pr.draft,
      url: pr.html_url,
      branch: pr.head && pr.head.ref,
      updatedAt: pr.updated_at
    }));
    const recentCommits = commits.map((commit) => ({
      sha: commit.sha.slice(0, 7),
      message: String(commit.commit && commit.commit.message || "").split("\n")[0],
      url: commit.html_url,
      at: commit.commit && commit.commit.committer && commit.commit.committer.date
    }));
    const workflows = (runs.workflow_runs || []).slice(0, 8).map((run) => ({
      name: run.name,
      status: run.status,
      conclusion: run.conclusion,
      event: run.event,
      branch: run.head_branch,
      url: run.html_url,
      at: run.updated_at
    }));

    return res.status(200).json({
      configured: true,
      repository: repo,
      state,
      pullRequests,
      commits: recentCommits,
      workflows,
      fetchedAt: new Date().toISOString()
    });
  } catch (error) {
    return res.status(502).json({
      configured: true,
      error: error instanceof Error ? error.message : String(error),
      state: fallbackState(),
      pullRequests: [], commits: [], workflows: []
    });
  }
};
