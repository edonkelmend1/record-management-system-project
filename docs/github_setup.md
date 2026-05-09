# GitHub Setup And Commit Guide

This file is for the team member who is responsible for creating the GitHub
repository first.

## Create The Repository

1. Install Git if it is not already available:
   <https://git-scm.com/downloads>
2. Create a new private or public GitHub repository.
3. Add the lecturer as a collaborator or give the lecturer access using the
   method requested by the course.
4. Open this project folder in a terminal.
5. Run these commands, replacing the remote URL with your repository URL:

```powershell
git init
git branch -M main
git add .
git commit -m "project: Add initial record management system."
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPO.git
git push -u origin main
```

## Commit Message Standard

The assignment refers to the PyInstaller 6.6.0 commit message guide:
<https://pyinstaller.org/en/v6.6.0/development/commit-messages.html>

Use these project rules:

- Commit one logical change at a time.
- Do not mix unrelated changes in the same commit.
- Keep the first line short, ideally 50 characters or fewer.
- Prefix the first line with a subsystem name.
- Use present tense.
- End the first line with a period.
- Add a body for larger changes, separated from the first line by a blank line.
- Wrap body lines at about 72 characters.

Good examples for this project:

```text
gui: Add record edit form.
storage: Save records as JSON.
tests: Cover flight record validation.
docs: Add report draft.
```

For a larger change:

```text
manager: Validate flight references.

Flights now require an existing client ID and airline ID before they can be
created. This prevents the system from storing bookings that cannot be linked
back to the client and airline records.
```

## Suggested First Team Workflow

1. Project manager creates a list of tasks and assigns roles.
2. Repository owner creates the GitHub repo and shares it with the team.
3. Programmer works on record logic and storage.
4. GUI/UX designer improves form layout and user flow.
5. Tester expands unit tests and checks edge cases.
6. Everyone pulls the latest code before making changes.

## Final Submission Checklist

- All team members have the same final code.
- Tests pass.
- Lecturer has repository access.
- The repository is zipped and uploaded to the VLE.
- The report is complete and around 1000 words.

