import mainCV

def userInput():
  # Automatically converts lowercase text to uppercase
  return input("Stand By: ").upper()


def run():
  print("AI IS RUNNING")
  mainCV.main_loop()

def main():
  while True:
    command = userInput()
    if command == "M112":
      run()
    elif command == "EXIT":
      break
    else:
      print(f"Unknown command: {command}")


if __name__ == "__main__":
  main()