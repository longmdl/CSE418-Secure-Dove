class AlertManager {
  constructor() {
    const container = document.querySelector("#alert-container");
    if (!container) {
      throw new Error(
        "Alert container element with id 'alert-container' not found!"
      );
    }
    this.container = container;
    this.alerts = new Map();
  }

  newAlert(message, type = "info", duration = 5000, title = "Alert") {
    const id = crypto.randomUUID();
    const alertElement = this.createAlertElement(id, message, type, title);

    this.container.append(alertElement);
    this.alerts.set(id, alertElement);

    if (duration > 0) {
      setTimeout(() => this.removeAlert(id), duration);
    }

    return id;
  }

  removeAlert(id) {
    const alert = this.alerts.get(id);
    if (alert) {
      alert.classList.add("opacity-0"); // Hide to fade out
      setTimeout(() => {
        alert.remove();
        this.alerts.delete(id);
      }, 300);
    }
  }

  clearAlerts() {
    this.alerts.forEach((_, id) => this.removeAlert(id));
  }

  getIconForType(type) {
    switch (type) {
      case "success":
        return "check-circle";
      case "error":
        return "alert-circle";
      case "warning":
        return "alert-triangle";
      default:
        return "info";
    }
  }

  createAlertElement(id, message, type = "info", title = "Alert") {
    // Allows for different colors for different alert types, targets h3 headers and svgs for icons aswell
    const colorClasses = {
      success: "border-green-500 [&_svg]:text-green-500 [&_h3]:text-green-500",
      error: "border-red-500 [&_svg]:text-red-500 [&_h3]:text-red-500",
      info: "border-blue-500 [&_svg]:text-blue-500 [&_h3]:text-blue-500",
      warning:
        "border-yellow-500 [&_svg]:text-yellow-500 [&_h3]:text-yellow-500",
    };

    const alert = document.createElement("div");
    // start hidden to allow fade in
    alert.className = `opacity-0 transition-all duration-300 transform translate-y-[-1rem] w-full p-4 bg-primary border-2 rounded-lg shadow-lg flex flex-col gap-2 ${colorClasses[type]} `;
      alert.id = id;

      //begin editing the contents to incorporate DOM for more security
      
      const divOuter = document.createElement("div");
      divOuter.className="flex justify-between items-center mb-2";

      const divInner = document.createElement("div");
      divInner.className="flex items-center gap-3";

      const icon = document.createElement("i");
      icon.setAttribute("data-lucide", this.getIconForType(type));
      icon.setAttribute("class", "w-6 h-6");

      const header3 = document.createElement("h3");
      header3.className="font-semibold text-xl";
      header3.textContent = title;

      const button = document.createElement("button");
      button.className="text-gray-400 hover:text-white";
      button.setAttribute("onclick", `alertManager.removeAlert('${id}')`);

      const xIcon = document.createElement("i");
      xIcon.setAttribute("data-lucide", "x");
      xIcon.className="w-5 h-5";

      const para = document.createElement("p");
      para.className="text-white leading-relaxed";
      para.textContent=message;

      button.appendChild(xIcon); //build individual elements to preserve HTML structure 
      divInner.appendChild(icon);
      divInner.appendChild(header3);
      
      divOuter.appendChild(divInner);
      divOuter.appendChild(button);
      
      alert.appendChild(divOuter);
      alert.appendChild(para); 
      

    // Let element render first, then remove opacity
    setTimeout(() => {
      alert.classList.remove("opacity-0");
      alert.classList.remove("translate-y-[-1rem]");
      lucide.createIcons({
        elements: alert.querySelectorAll("[data-lucide]"),
      });
    }, 100);

    return alert;
  }
}

// Global variable for alertManager
const alertManager = new AlertManager();
