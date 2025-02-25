// Demo function callimport axios from 'axios';
import axios from "axios";

interface Assistant {
  id: string;
  name: string;
  // Add other assistant properties as needed
}

interface Thread {
  id: string;
  // Add other thread properties as needed
}

interface Run {
  id: string;
  status: string;
  // Add other run properties as needed
}

interface Message {
  role: string;
  content: string;
}

const API_BASE_URL = "https://pvpvai.com/promptbet-agent";

const searchAndCreateRun = async () => {
  try {
    // 1. Search for agents
    const searchResponse = await axios.post<{ assistants: Assistant[] }>(
      `${API_BASE_URL}/assistants/search`,
      { query: "betting_pool_generator" },
      {
        headers: {
          //   'Authorization': `Bearer ${API_KEY}`,
          "Content-Type": "application/json",
        },
      }
    );

    console.log("searchResponse", searchResponse.data);

    // 2. Find the betting pool generator assistant
    const bettingPoolAssistant = searchResponse.data.find(
      (assistant) => assistant.name === "betting_pool_generator"
    );

    console.log("bettingPoolAssistant", bettingPoolAssistant);

    if (!bettingPoolAssistant) {
      throw new Error("Betting pool generator assistant not found");
    }

    // 3. Create a thread
    const threadResponse = await axios.post<Thread>(
      `${API_BASE_URL}/threads`,
      {
        thread_id: "",
        metadata: {},
        if_exists: "raise",
      },
      {
        headers: {
          //   'Authorization': `Bearer ${API_KEY}`,
          "Content-Type": "application/json",
        },
      }
    );
    console.log("bettingPoolAssistant.id", bettingPoolAssistant.id);
    console.log("thread id", threadResponse.data.thread_id);
    console.log("thread response", threadResponse.data);

    // 4. Create a run
    const runResponse = await axios.post<Run>(
      `${API_BASE_URL}/threads/${threadResponse.data.thread_id}/runs/wait`,
      {
        assistant_id: bettingPoolAssistant.assistant_id,
        input: {
          messages: [
            {
              role: "user",
              content: "Generate a betting pool for me",
            },
          ],
        },
      },
      {
        headers: {
          //   'Authorization': `Bearer ${API_KEY}`,
          "Content-Type": "application/json",
        },
      }
    );

    console.log("runResponse", runResponse.data);
    return runResponse.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      console.error("API Error:", error.response?.data);
    }
    throw error;
  }
};

// Usage
searchAndCreateRun()
  .then((result) => console.log("Run created:", result))
  .catch((error) => console.error("Error:", error));
