# Get current branch
$currentBranch = git rev-parse --abbrev-ref HEAD

# Get all local branches
$branches = git for-each-ref --format='%(refname:short)' refs/heads/

foreach ($branch in $branches) {
    Write-Host "Processing branch: $branch"
    
    # Checkout the branch
    git checkout $branch
    
    # Create temporary branch with the current content
    git checkout --orphan temp-$branch
    
    # Add all files
    git add .
    
    # Commit with a message referencing it's the latest state of the branch
    git commit -m "Latest state of $branch (history reset)"
    
    # Delete the original branch
    git branch -D $branch
    
    # Rename temp branch to original
    git branch -m $branch
}

# Return to original branch
git checkout $currentBranch

Write-Host "All branches have been reset to their latest commit only."