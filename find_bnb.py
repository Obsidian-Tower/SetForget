# find_bnb_lines.py

def print_bnb_lines(log_file_path):
    try:
        with open(log_file_path, 'r', encoding='utf-8') as file:
            for line in file:
                if 'BNB' in line:
                    print(line.rstrip())
    except FileNotFoundError:
        print(f"Error: File '{log_file_path}' not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    log_file_path = "gridbot.log"  # Update this if the file is in another directory
    print_bnb_lines(log_file_path)
