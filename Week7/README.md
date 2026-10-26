<!--
  FOR YOUR REFERENCE (FYR): a template for the README.md of your own GitHub repository.

  HOW TO USE THIS TEMPLATE
  1. Copy this file into your project folder and rename it to README.md.
  2. Replace every part in [square brackets] with your own words. Delete the example text you do not need.
  3. Delete these comment blocks (the grey notes like this one). GitHub does not show comments,
     but a clean file is easier to read.
  4. Put your screenshots in a folder named images/ in your project, and check that they show on GitHub.
-->

# [Your Agent's Name]: [One Line About What It Does]

<!-- Example: # Little Prince Guesthouse Helper: Answers Questions About Rooms, Prices and Check-In -->

[Two or three sentences. Which shop or office is this agent for, who uses it, and what problem does it solve?]

> Course homework: Unit G, My AI Customer Service Agent, with a Database and Tools
> Student: [Student ID] [Your Name]

![Main screen of my agent, with the tool trace](images/screenshot-main.png)

## Who It Serves and When They Use It

- **Who uses it:** [for example, guests who want to book a room or ask about check-in]
- **When they use it:** [for example, at night, when nobody can answer the phone]
- **What problem it solves:** [for example, the same questions about prices and parking come in every day]

## What It Can Do

| Function | Example question | Tool it uses |
|---|---|---|
| [Tell the check-in time and the address] | "What time can I check in?" | [`get_info`] |
| [Find a free room] | "Do you have a double room this Friday?" | [`search_rooms`] |
| [Work out the price of a stay] | "How much are three nights in a double room?" | [`calculate_stay`] |
| [Hand over to a person] | "I want to make a complaint." | [`transfer_to_human`] |

## How It Works

Every question goes to the agent first. The agent chooses a tool, the tool reads the database
or calculates in code, and the agent answers only from what the tool returns.

- **Model:** [for example, gemini-3.5-flash-lite]
- **Chat screen:** [for example, Gradio, or Flask + HTML, or React Native]
- **Database (SQLite):** built from the CSV files every time the program starts.

  | Table | CSV file | What it holds | Rows |
  |---|---|---|---|
  | [`shop_info`] | [`shop_info.csv`] | [topics such as opening hours, address, parking] | [10] |
  | [`rooms`] | [`rooms.csv`] | [room types, prices, available or not] | [16] |

- **Tools:**

  | Tool | What it does |
  |---|---|
  | [`get_info(topic)`] | [reads one topic from `shop_info`] |
  | [`search_rooms(keyword)`] | [finds rooms in `rooms`] |
  | [`calculate_stay(room, nights)`] | [nights × price, calculated in code] |
  | [`transfer_to_human()`] | [gives the staff phone number] |

## Sample Conversations

<!-- Add 2 or 3 screenshots that show the tool trace. One should use the calculation tool,
     and one should show a question that your data does not cover. -->

![A question that uses the calculation tool](images/screenshot-1.png)

![A question the data does not cover](images/screenshot-2.png)

## Project Files

```text
my-customer-service/
├── app.py              # the agent: database, tools, agent loop and chat screen
├── shop_info.csv       # the information table
├── rooms.csv           # the records table
├── requirements.txt    # the Python packages to install
├── .env.example        # a sample settings file (no real key)
├── .gitignore          # files git must not upload: .env and *.db
├── images/             # screenshots for this README
└── README.md           # this file
```

<!-- Change this list to match your own files. The .db file is not here:
     the program builds it from the CSV files. -->

## How to Install and Run It

1. Download the project:

   ```bash
   git clone https://github.com/[your-account]/[your-repo].git
   cd [your-repo]
   ```

2. Install the packages (Python 3.10 or newer):

   ```bash
   pip install -r requirements.txt
   ```

3. Make your settings file. Copy `.env.example` to `.env`, then put your own API key after `API_KEY=`.
   The model must support tool calling.

   ```bash
   copy .env.example .env      # Windows
   cp .env.example .env        # macOS or Linux
   ```

4. Start the agent. It builds the database from the CSV files, then opens the chat page:

   ```bash
   python app.py
   ```

5. Open the link shown in the console, usually <http://127.0.0.1:7860>.

<!-- If you used another framework or a mobile app, write your own steps here,
     for example: npm install, npm run dev, or flutter run. -->

## Notes

- All names, phone numbers, prices and bookings in the data are **made up**. [If you used public information
  from a real shop or office, say where it came from.]
- The `.env` file holds the API key. It is **not** in this repository. Make your own from `.env.example`.
- [Anything else the reader should know, for example the limits of the agent or ideas for the next version.]
