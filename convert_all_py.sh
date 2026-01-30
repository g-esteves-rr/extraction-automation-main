#!/bin/bash

# Set dry-run mode (true/false)
DRY_RUN=false

# Directories to exclude
EXCLUDE_DIRS=(
    "./env_automation"
    "./00_extras"
)

# Initialize counters and associative arrays
declare -A changed_files_per_dir
declare -A total_files_per_dir
total_files=0
total_changed=0
success_count=0
fail_count=0

# Get current directory
CURRENT_DIR=$(pwd)

# Count files in a directory recursively
count_files_in_dir() {
    find "$1" -type f -name "*.py" | wc -l
}

# Count files in root directory
root_files=$(count_files_in_dir "$CURRENT_DIR")
total_files_per_dir["ROOT"]=$root_files

# Process files outside excluded directories
while IFS= read -r filename; do
    total_files=$((total_files + 1))
    # Determine directory of the file
    dir_of_file=$(dirname "$filename")
    rel_dir="${dir_of_file#./}"
    rel_dir=${rel_dir:-ROOT}

    # Count files in this directory if not already counted
    if [ -z "${total_files_per_dir[$rel_dir]}" ]; then
        total_files_per_dir[$rel_dir]=$(count_files_in_dir "$dir_of_file")
    fi

    echo "Processing: $filename"

    if [ "$DRY_RUN" = true ]; then
        echo "[DRY-RUN] Would run: dos2unix \"$filename\""
        echo "Status: Success (dry-run)"
        # Count as changed in this directory
        changed_files_per_dir[$rel_dir]=$(( ${changed_files_per_dir[$rel_dir]:-0} + 1 ))
        total_changed=$((total_changed + 1))
        success_count=$((success_count + 1))
    else
        if dos2unix "$filename"; then
            echo "Status: Success"
            # Count as changed in this directory
            changed_files_per_dir[$rel_dir]=$(( ${changed_files_per_dir[$rel_dir]:-0} + 1 ))
            total_changed=$((total_changed + 1))
            success_count=$((success_count + 1))
        else
            echo "Status: Failed"
            fail_count=$((fail_count + 1))
        fi
    fi
done < <(find . \( -path "./env_automation" -o -path "./00_extras" \) -prune -o -type f -name "*.py" -print)

# Count files in current directory
current_dir_files=$(count_files_in_dir ".")

# Function to print directory counts hierarchically
print_dir_counts() {
    local dir="$1"
    local prefix="$2"
    local count="${total_files_per_dir[$dir]}"
    echo "$prefix$dir : $count"
    # Find subdirectories
    local subdirs=()
    while IFS= read -r subdir; do
        subdirs+=("$subdir")
    done < <(find "$dir" -mindepth 1 -maxdepth 1 -type d \( \( -path "./env_automation" -o -path "./00_extras" \) -prune -false \) -print)

    for sub in "${subdirs[@]}"; do
        rel_sub="${sub#./}"
        print_dir_counts "$rel_sub" "$prefix  "
    done
}

# Print counts starting from root
echo -e "\n==================== Summary ===================="
print_dir_counts "." "  "

# Print overall stats
echo "Total files in root: $current_dir_files"
echo "Total files processed: $total_files"
echo "Successfully changed: $success_count"
echo "Failed to change:  $fail_count"
echo "Total files changed: $total_changed"
echo "Excluded directories: ${EXCLUDE_DIRS[*]}"
echo "=================================================="
