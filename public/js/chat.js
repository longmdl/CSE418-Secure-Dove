function generateMessage(message){ //to generate safe HTML with variables
      const divOuterFirst = document.createElement("div");
      divOuterFirst.id=`group-${message.id}`;
      divOuterFirst.className="py-1";
      const divMiddleFirst = document.createElement("div");
      divMiddleFirst.id = `message-${message.id}`;
      divMiddleFirst.className= "flex items-start gap-2 group"; 
      const divInnerFirst = document.createElement("div");
      divInnerFirst.className="flex items-center h-full self-center";
      const buttonFirst = document.createElement("button");
      buttonFirst.className="text-xs px-1 py-0.5 rounded bg-gray-600 text-white hover:bg-gray-500";
      buttonFirst.id="delete-button";
      buttonFirst.setAttribute("onclick", `deleteMessage('${message.id}')`);
      buttonFirst.textContent="X";

      const divOuterSecond = document.createElement("div");
      divOuterSecond.className = "relative flex flex-col h-full justify-center";
      const paraSecond = document.createElement("p");
      const divInnerSecond = document.createElement("div");
      divInnerSecond.id=message.id;
      divInnerSecond.className="cursor-pointer message-content";
      const spanFirst=document.createElement("span");
      spanFirst.className="italic font-black";
      spanFirst.textContent=`${message.author} :`; 
      const spanSecond = document.createElement("span");
      spanSecond.className="whitespace-pre-wrap";
      spanSecond.textContent=message.content;
      const spanThird = document.createElement("span");
      spanThird.className="text-xs";
      spanThird.textContent = message.updated ? "(edited)" : "";
      const buttonSecond=document.createElement("button");
      buttonSecond.className="absolute top-0 -right-6 p-1 hover:bg-gray-200/50 rounded-full";
      buttonSecond.setAttribute("onclick", `editMessage('${message.id}')`);
      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("width", "14");
      svg.setAttribute("height", "14"); 
      svg.setAttribute("viewBox", "0 0 24 24");
      svg.setAttribute("fill", "none");
      svg.setAttribute("stroke", "currentColor"); 
      svg.setAttribute("stroke-width", "2"); 
      svg.setAttribute("stroke-linecap", "round");
      svg.setAttribute("stroke-linejoin", "round");
      svg.setAttribute("class", "text-gray-600");
      const pathFirst = document.createElementNS("http://www.w3.org/2000/svg","path"); 
      pathFirst.setAttribute("d", "M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z");
      const pathSecond = document.createElementNS("http://www.w3.org/2000/svg","path");
      pathSecond.setAttribute("d", "m15 5 4 4");

      const divOuterThird=document.createElement("div");
      divOuterThird.className = "hidden flex items-start gap-2 mb-2"; 
      divOuterThird.id = `edit-form-${message.id}`;
      const formFirst = document.createElement("form");
      formFirst.className = "w-full"; 
      formFirst.setAttribute("onsubmit",`event.preventDefault(); submitEdit('${message.id}')`);
      const divMiddleThird=document.createElement("div"); 
      divMiddleThird.className="flex gap-2 items-center";
      const spanFourth = document.createElement("span");
      spanFourth.className="text-sm";
      spanFourth.textContent=`${message.author}:`;
      const inputFirst=document.createElement("input");
      inputFirst.type="text";
      inputFirst.className= "flex-1 px-2 py-1 border rounded";
      inputFirst.value = message.content; 
      inputFirst.id = `edit-input-${message.id}`; 
      const divInnerThird = document.createElement("div");
      divInnerThird.className="flex gap-2 mt-2 justify-start";
      const buttonThird=document.createElement("button");
      buttonThird.type = "button"; 
      buttonThird.className = "px-2 py-1 text-sm rounded bg-gray-700 hover:bg-gray-300"; 
      buttonThird.textContent = "Cancel";
      buttonThird.setAttribute("onclick", `cancelEdit('${message.id}');`);
      const buttonFourth=document.createElement("button");
      buttonFourth.type = "button"; 
      buttonFourth.className = "px-2 py-1 text-sm rounded bg-blue-500 text-white hover:bg-blue-600"; 
      buttonFourth.textContent = "Save";
      buttonFourth.type="submit";
      
      divInnerFirst.appendChild(buttonFirst);
      divInnerSecond.appendChild(spanFirst);
      divInnerSecond.appendChild(spanSecond);
      divInnerSecond.appendChild(spanThird);
      svg.appendChild(pathFirst);
      svg.appendChild(pathSecond);
      buttonSecond.appendChild(svg);
      paraSecond.appendChild(divInnerSecond);
      paraSecond.appendChild(buttonSecond);
      divOuterSecond.appendChild(paraSecond);

      divMiddleFirst.appendChild(divInnerFirst);
      divMiddleFirst.appendChild(divOuterSecond);
      divMiddleThird.appendChild(spanFourth);
      divMiddleThird.appendChild(inputFirst);
      divInnerThird.appendChild(buttonThird);
      divInnerThird.appendChild(buttonFourth);

      formFirst.appendChild(divMiddleThird);
      formFirst.appendChild(divInnerThird);
      divOuterThird.appendChild(formFirst);
      divOuterFirst.appendChild(divMiddleFirst);
      divOuterFirst.appendChild(divOuterThird);

      return divOuterFirst;
    }

async function fetchMessages() {
  const newMessages = await fetch("/api/chats").then((res) => res.json());
  newMessages.messages.forEach((message) => {
    if (message.id === isEditing) {
      return;
    }
    //update message
    const messageSection=generateMessage(message);
    const groupRef = document.getElementById(`group-${message.id}`);
    if (groupRef === null) {
      document.getElementById("messages").appendChild(messageSection);
      return;
    }
    groupRef.replaceWith(messageSection);
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
