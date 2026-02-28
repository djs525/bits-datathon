# Contributor Guidelines

Welcome! To ensure our project remains stable with 5 contributors, please follow this workflow.

## Branching Strategy

1.  **Main Branch**: The `main` branch is for stable, production-ready code. Never push directly to `main`.
2.  **Feature Branches**: Create a new branch for every feature or bug fix.
    ```bash
    git checkout -b feature/your-feature-name
    ```

## Development Workflow

1.  **Pull Frequently**: Before starting work, pull the latest changes from `main`.
    ```bash
    git checkout main
    git pull origin main
    git checkout feature/your-feature-name
    git merge main
    ```
2.  **Write Tests**: Ensure every new feature has corresponding tests in `tests/` or `frontend/src/`.
3.  **Local Verification**: Before pushing, run the verification script.
    ```bash
    ./pre-push.sh
    ```
4.  **Push and Pull Request**:
    - Push your feature branch to GitHub.
    - Open a Pull Request (PR) to merge into `main`.
    - At least one other contributor must review and approve your PR.
    - Automated tests must pass (check the GitHub Actions tab).

## Commit Messages

Use clear, descriptive commit messages.
- `feat: add smart defaults to predict endpoint`
- `fix: resolve crash when zip code is missing`
- `docs: update contributor guidelines`
