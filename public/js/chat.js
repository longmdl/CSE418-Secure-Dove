import { html } from "./utils.js";

async function fetchMessages() {
  const newMessages = await fetch("/api/chats").then((res) => res.json());
  newMessages.messages.forEach((message) => {
    if (message.id === isEditing) {
      return;
    }
    const messageHtml = html`
      <div id="group-${message.id}" class="py-1">
        <div id="message-${message.id}" class="flex items-start gap-2 group">
          <div class="flex items-center h-full self-center">
            <button
            class="text-xs px-1 py-0.5 rounded bg-gray-600 text-white hover:bg-gray-500"
            id="delete-button"
            onclick="deleteMessage('${message.id}')"
            >
            X
            </button>
          </div>
          <div class="relative flex flex-col h-full justify-center">
            <p>
              <div class="cursor-pointer message-content" id="${message.id}">
                <span class="italic font-black">${message.author} :</span>
                <span 
                  >${message.content}</span
                >
                <span class="text-xs">${message.updated ? "(edited)" : ""
      } </span>
              </div>
              <button
                class="absolute top-0 -right-6 p-1 hover:bg-gray-200/50 rounded-full"
                onclick="editMessage('${message.id}')"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  class="text-gray-600"
                >
                  <path
                    d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"
                  />
                  <path d="m15 5 4 4" />
                </svg>
              </button>
            </p>
          </div>
        </div>

        <div
          class="hidden flex items-start gap-2 mb-2"
          id="edit-form-${message.id}"
        >
          <form
            class="w-full"
            onsubmit="event.preventDefault(); submitEdit('${message.id}')"
          >
            <div class="flex gap-2 items-center">
              <span class="text-sm">${message.author}:</span>
              <input
                type="text"
                class="flex-1 px-2 py-1 border rounded"
                value="${message.content}"
                id="edit-input-${message.id}"
              />
            </div>
            <div class="flex gap-2 mt-2 justify-start">
              <button
                type="button"
                class="px-2 py-1 text-sm rounded bg-gray-700 hover:bg-gray-300"
                onclick="cancelEdit('${message.id}')"
              >
                Cancel
              </button>
              <button
                class="px-2 py-1 text-sm rounded bg-blue-500 text-white hover:bg-blue-600"
                type="submit"
              >
                Save
              </button>
            </div>
          </form>
        </div>
      </div>
    `;
    const groupRef = document.getElementById(`group-${message.id}`);
    if (groupRef === null) {
      document
        .getElementById("messages")
        .insertAdjacentHTML("beforeend", messageHtml);
      return;
    }
    groupRef.outerHTML = messageHtml;
  });

  // Remove deleted messages
  document.querySelectorAll('[id^="group-"]').forEach((element) => {
    const id = element.id.replace("group-", "");
    // console.log("message group id:", id);
    const isDeleted = !newMessages.messages.find(
      (message) => message.id === id
    );
    if (isDeleted) {
      const element = document.getElementById(`group-${id}`);
      if (element) {
        element.remove();
      }
    }
  });

}

fetchMessages();
setInterval(fetchMessages, 1000);
let isEditing = null;

function editMessage(messageId) {
  document.getElementById(`message-${messageId}`).classList.add("hidden");
  document.getElementById(`edit-form-${messageId}`).classList.remove("hidden");
  document.getElementById(`edit-input-${messageId}`).focus();

  // Weird quirk to move cursor to front of text
  const temp = document.getElementById(`edit-input-${messageId}`).value;
  document.getElementById(`edit-input-${messageId}`).value = "";
  document.getElementById(`edit-input-${messageId}`).value = temp;

  isEditing = messageId;
}

async function sendMessage(event) {
  event.preventDefault();
  const content = document.getElementById("new-message").value;

  try {
    const response = await fetch("/api/chats", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ content }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      alertManager.newAlert(errorText, "error", 5000, "Failed to Send Message");
      return;
    }

    document.getElementById("new-message").value = "";
  } catch (error) {
    alertManager.newAlert(
      "Failed to send message. Please try again.",
      "error",
      5000,
      "Error"
    );
  }
}

async function deleteMessage(id) {
  try {
    const response = await fetch(`/api/chats/${id}`, { method: "DELETE" });

    if (!response.ok) {
      const errorText = await response.text();
      alertManager.newAlert(
        errorText,
        "error",
        5000,
        "Failed to Delete Message"
      );
      return;
    }
  } catch (error) {
    alertManager.newAlert(
      "Failed to delete message. Please try again.",
      "error",
      5000,
      "Error"
    );
  }
}

async function patchMessage(messageId, newContent) {
  try {
    const response = await fetch(`/api/chats/${messageId}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ content: newContent }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      alertManager.newAlert(
        errorText,
        "error",
        5000,
        "Failed to Update Message"
      );
      return;
    }
  } catch (error) {
    alertManager.newAlert(
      "Failed to update message. Please try again.",
      "error",
      5000,
      "Error"
    );
  }
}

function cancelEdit(messageId) {
  document.getElementById(`message-${messageId}`).classList.remove("hidden");
  document.getElementById(`edit-form-${messageId}`).classList.add("hidden");
  isEditing = null;
}

function submitEdit(messageId) {
  const newContent = document.getElementById(`edit-input-${messageId}`).value;
  patchMessage(messageId, newContent);
  cancelEdit(messageId);
}

window.sendMessage = sendMessage;
window.deleteMessage = deleteMessage;
window.editMessage = editMessage;
window.submitEdit = submitEdit;
window.cancelEdit = cancelEdit;
