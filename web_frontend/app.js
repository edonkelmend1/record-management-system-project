const CLIENT = "Client";
const AIRLINE = "Airline";
const FLIGHT = "Flight";
const STORAGE_KEY = "record-management-system.records";

const fieldsByType = {
  [CLIENT]: [
    "Name",
    "Address Line 1",
    "Address Line 2",
    "Address Line 3",
    "City",
    "State",
    "Zip Code",
    "Country",
    "Phone Number",
  ],
  [AIRLINE]: ["Company Name"],
  [FLIGHT]: ["Client_ID", "Airline_ID", "Date", "Start City", "End City"],
};

const exampleRecords = [
  {
    ID: 1,
    Type: CLIENT,
    Name: "Maria Lopez",
    "Address Line 1": "",
    "Address Line 2": "",
    "Address Line 3": "",
    City: "Madrid",
    State: "",
    "Zip Code": "",
    Country: "Spain",
    "Phone Number": "+34 600 000 000",
  },
  {
    ID: 2,
    Type: CLIENT,
    Name: "John Smith",
    "Address Line 1": "",
    "Address Line 2": "",
    "Address Line 3": "",
    City: "London",
    State: "",
    "Zip Code": "",
    Country: "UK",
    "Phone Number": "+44 7000 000000",
  },
  {
    ID: 3,
    Type: CLIENT,
    Name: "Anna Keller",
    "Address Line 1": "",
    "Address Line 2": "",
    "Address Line 3": "",
    City: "Zurich",
    State: "",
    "Zip Code": "",
    Country: "Switzerland",
    "Phone Number": "+41 79 000 000",
  },
  {
    ID: 1,
    Type: AIRLINE,
    "Company Name": "Swiss",
  },
  {
    ID: 2,
    Type: AIRLINE,
    "Company Name": "British Airways",
  },
  {
    ID: 3,
    Type: AIRLINE,
    "Company Name": "Lufthansa",
  },
  {
    Type: FLIGHT,
    Client_ID: 1,
    Airline_ID: 1,
    Date: "2026-05-15 00:00",
    "Start City": "Zurich",
    "End City": "Madrid",
  },
  {
    Type: FLIGHT,
    Client_ID: 2,
    Airline_ID: 2,
    Date: "2026-05-20 00:00",
    "Start City": "London",
    "End City": "Paris",
  },
  {
    Type: FLIGHT,
    Client_ID: 3,
    Airline_ID: 3,
    Date: "2026-05-25 00:00",
    "Start City": "Zurich",
    "End City": "Berlin",
  },
];

let records = loadRecords();
let selectedIndex = null;
let sortColumn = null;
let sortReverse = false;
let activeType = CLIENT;

const elements = {
  body: document.getElementById("records-body"),
  head: document.getElementById("table-head"),
  typeFilter: document.getElementById("record-type-filter"),
  searchText: document.getElementById("search-text"),
  searchLabel: document.getElementById("search-label"),
  clientFlightFilter: document.getElementById("client-flight-filter"),
  airlineFlightFilter: document.getElementById("airline-flight-filter"),
  status: document.getElementById("status-message"),
  formType: document.getElementById("form-type"),
  formPanel: document.getElementById("form-panel"),
  formTitle: document.getElementById("form-title"),
  form: document.getElementById("record-form"),
  formFields: document.getElementById("form-fields"),
  createButton: document.getElementById("create-record"),
  updateButton: document.getElementById("update-record"),
  deleteButton: document.getElementById("delete-record"),
  deleteModal: document.getElementById("delete-modal"),
  importJson: document.getElementById("import-json"),
};

const tableColumns = {
  [CLIENT]: [
    ["id", "ID"],
    ["name", "Name"],
    ["city", "City"],
    ["country", "Country"],
    ["phone", "Phone Number"],
  ],
  [AIRLINE]: [
    ["id", "ID"],
    ["company", "Company Name"],
  ],
  [FLIGHT]: [
    ["client", "Client"],
    ["airline", "Airline"],
    ["route", "Route"],
    ["date", "Date"],
  ],
};

function loadRecords() {
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (!stored) {
    return structuredClone(exampleRecords);
  }
  try {
    const parsed = JSON.parse(stored);
    if (!Array.isArray(parsed)) {
      return [];
    }
    validateAllRecords(parsed);
    return parsed;
  } catch (_error) {
    return [];
  }
}

function saveRecords() {
  validateAllRecords(records);
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(records, null, 2));
}

function cleanText(value) {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value).trim();
}

function parsePositiveInt(value, fieldName) {
  const text = cleanText(value);
  if (!/^\d+$/.test(text)) {
    throw new Error(`${fieldName} must be a positive integer.`);
  }
  const parsed = Number.parseInt(text, 10);
  if (parsed <= 0) {
    throw new Error(`${fieldName} must be a positive integer.`);
  }
  return parsed;
}

function normaliseDate(value) {
  const text = cleanText(value);
  if (!text) {
    throw new Error("Date is required.");
  }
  const parsed = new Date(text);
  if (Number.isNaN(parsed.getTime())) {
    throw new Error("Date must use ISO format, for example 2026-05-09.");
  }
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) {
    return `${text} 00:00`;
  }
  return text.replace("T", " ");
}

function nextId(recordType) {
  return records
    .filter((record) => record.Type === recordType)
    .reduce((highest, record) => Math.max(highest, Number(record.ID) || 0), 0) + 1;
}

function buildClient(values, existingId = null) {
  const name = cleanText(values.Name);
  const phone = cleanText(values["Phone Number"]);
  if (!name) {
    throw new Error("Name is required.");
  }
  if (!phone) {
    throw new Error("Phone Number is required.");
  }
  return {
    ID: parsePositiveInt(existingId || nextId(CLIENT), "ID"),
    Type: CLIENT,
    Name: name,
    "Address Line 1": cleanText(values["Address Line 1"]),
    "Address Line 2": cleanText(values["Address Line 2"]),
    "Address Line 3": cleanText(values["Address Line 3"]),
    City: cleanText(values.City),
    State: cleanText(values.State),
    "Zip Code": cleanText(values["Zip Code"]),
    Country: cleanText(values.Country),
    "Phone Number": phone,
  };
}

function buildAirline(values, existingId = null) {
  const companyName = cleanText(values["Company Name"]);
  if (!companyName) {
    throw new Error("Company Name is required.");
  }
  return {
    ID: parsePositiveInt(existingId || nextId(AIRLINE), "ID"),
    Type: AIRLINE,
    "Company Name": companyName,
  };
}

function buildFlight(values, recordList = records) {
  const startCity = cleanText(values["Start City"]);
  const endCity = cleanText(values["End City"]);
  if (!startCity) {
    throw new Error("Start City is required.");
  }
  if (!endCity) {
    throw new Error("End City is required.");
  }
  const record = {
    Type: FLIGHT,
    Client_ID: parsePositiveInt(values.Client_ID, "Client_ID"),
    Airline_ID: parsePositiveInt(values.Airline_ID, "Airline_ID"),
    Date: normaliseDate(values.Date),
    "Start City": startCity,
    "End City": endCity,
  };
  validateFlightReferences(record, recordList);
  return record;
}

function buildRecord(recordType, values, existingRecord = null, recordList = records) {
  if (recordType === CLIENT) {
    return buildClient(values, existingRecord ? existingRecord.ID : null);
  }
  if (recordType === AIRLINE) {
    return buildAirline(values, existingRecord ? existingRecord.ID : null);
  }
  if (recordType === FLIGHT) {
    return buildFlight(values, recordList);
  }
  throw new Error("Record type is invalid.");
}

function validateAllRecords(recordList) {
  recordList.forEach((record) => validateRecord(record, recordList));
  recordList
    .filter((record) => record.Type === FLIGHT)
    .forEach((record) => validateFlightReferences(record, recordList));
}

function validateRecord(record, recordList = records) {
  if (!record || typeof record !== "object") {
    throw new Error("Record must be an object.");
  }
  if (!fieldsByType[record.Type]) {
    throw new Error("Record Type is invalid.");
  }
  buildRecord(record.Type, record, record, recordList);
  if (record.Type === FLIGHT) {
    validateFlightReferences(record, recordList);
  }
}

function validateFlightReferences(record, recordList = records) {
  const clientExists = recordList.some(
    (item) => item.Type === CLIENT && item.ID === record.Client_ID
  );
  if (!clientExists) {
    throw new Error("Client_ID must refer to an existing client record.");
  }
  const airlineExists = recordList.some(
    (item) => item.Type === AIRLINE && item.ID === record.Airline_ID
  );
  if (!airlineExists) {
    throw new Error("Airline_ID must refer to an existing airline record.");
  }
}

function getRecordName(recordType, recordId) {
  const record = records.find((item) => item.Type === recordType && item.ID === recordId);
  if (!record) {
    return "";
  }
  return recordType === CLIENT ? record.Name : record["Company Name"];
}

function namedReference(recordType, recordId) {
  const name = getRecordName(recordType, recordId);
  return name ? `${name} (#${recordId})` : String(recordId);
}

function summarizeRecord(record) {
  if (record.Type === CLIENT) {
    return `Client #${record.ID}: ${record.Name}`;
  }
  if (record.Type === AIRLINE) {
    return `Airline #${record.ID}: ${record["Company Name"]}`;
  }
  if (record.Type === FLIGHT) {
    return `Flight: ${namedReference(CLIENT, record.Client_ID)} with ${namedReference(
      AIRLINE,
      record.Airline_ID
    )}`;
  }
  return record.Type || "";
}

function recordDetails(record) {
  if (record.Type === CLIENT) {
    return [record.City, record.Country, record["Phone Number"]]
      .map(cleanText)
      .filter(Boolean)
      .join(" | ");
  }
  if (record.Type === AIRLINE) {
    return record["Company Name"];
  }
  if (record.Type === FLIGHT) {
    return `${record.Date}: ${record["Start City"]} to ${record["End City"]} | Client: ${namedReference(
      CLIENT,
      record.Client_ID
    )} | Airline: ${namedReference(AIRLINE, record.Airline_ID)}`;
  }
  return "";
}

function optionValue(record) {
  if (record.Type === CLIENT) {
    return `${record.ID} - ${record.Name}`;
  }
  return `${record.ID} - ${record["Company Name"]}`;
}

function idFromChoice(choice) {
  if (!choice.includes(" - ")) {
    return null;
  }
  const parsed = Number.parseInt(choice.split(" - ", 1)[0], 10);
  return Number.isNaN(parsed) ? null : parsed;
}

function refreshOptionLists() {
  fillRecordFilter(elements.clientFlightFilter, CLIENT, "All clients");
  fillRecordFilter(elements.airlineFlightFilter, AIRLINE, "All airlines");

  document.querySelectorAll("[data-field='Client_ID']").forEach((select) => {
    fillRecordFilter(select, CLIENT, "Choose a client", false);
  });
  document.querySelectorAll("[data-field='Airline_ID']").forEach((select) => {
    fillRecordFilter(select, AIRLINE, "Choose an airline", false);
  });
}

function fillRecordFilter(select, recordType, firstLabel, keepCurrent = true) {
  const current = keepCurrent ? select.value : "";
  select.replaceChildren();
  select.append(new Option(firstLabel, ""));
  records
    .filter((record) => record.Type === recordType)
    .forEach((record) => {
      select.append(new Option(optionValue(record), String(record.ID)));
    });
  if (keepCurrent && [...select.options].some((option) => option.value === current)) {
    select.value = current;
  }
}

function drawForm() {
  const recordType = elements.formType.value;
  elements.formTitle.textContent = `${recordType} Details`;
  elements.createButton.textContent = `Save ${recordType}`;
  elements.formFields.replaceChildren();

  fieldsByType[recordType].forEach((field) => {
    const wrapper = document.createElement("div");
    wrapper.className = "field";
    const label = document.createElement("label");
    label.textContent = field === "Client_ID" ? "Client" : field === "Airline_ID" ? "Airline" : field;
    label.htmlFor = `field-${field.replaceAll(" ", "-")}`;

    const input = document.createElement(field === "Client_ID" || field === "Airline_ID" ? "select" : "input");
    input.id = label.htmlFor;
    input.dataset.field = field;
    if (field === "Date") {
      input.type = "date";
    }
    wrapper.append(label, input);
    elements.formFields.append(wrapper);
  });

  refreshOptionLists();
}

function formValues() {
  const values = {};
  elements.formFields.querySelectorAll("[data-field]").forEach((input) => {
    const field = input.dataset.field;
    values[field] = field === "Client_ID" || field === "Airline_ID" ? input.value : input.value;
  });
  return values;
}

function setFormValues(record) {
  elements.formType.value = record.Type;
  drawForm();
  elements.formFields.querySelectorAll("[data-field]").forEach((input) => {
    const field = input.dataset.field;
    if (field === "Client_ID") {
      input.value = String(record.Client_ID);
    } else if (field === "Airline_ID") {
      input.value = String(record.Airline_ID);
    } else if (field === "Date") {
      input.value = cleanText(record.Date).slice(0, 10);
    } else {
      input.value = record[field] || "";
    }
  });
}

function clearForm() {
  selectedIndex = null;
  elements.form.reset();
  elements.formType.value = activeType;
  drawForm();
  hideFormPanel();
  render();
}

function showFormPanel() {
  elements.formPanel.classList.remove("hidden");
}

function hideFormPanel() {
  elements.formPanel.classList.add("hidden");
}

function filteredRows() {
  const query = elements.searchText.value.trim().toLowerCase();
  const typeFilter = elements.typeFilter.value === "All" ? activeType : elements.typeFilter.value;
  const clientId = elements.clientFlightFilter.value
    ? Number.parseInt(elements.clientFlightFilter.value, 10)
    : null;
  const airlineId = elements.airlineFlightFilter.value
    ? Number.parseInt(elements.airlineFlightFilter.value, 10)
    : null;

  let rows = records.map((record, index) => ({ index, record }));
  if (typeFilter !== "All") {
    rows = rows.filter(({ record }) => record.Type === typeFilter);
  }
  if (query) {
    rows = rows.filter(({ record }) =>
      Object.values(record).some((value) => String(value).toLowerCase().includes(query))
    );
  }
  if (clientId !== null || airlineId !== null) {
    elements.typeFilter.value = FLIGHT;
    rows = rows.filter(({ record }) => {
      if (record.Type !== FLIGHT) {
        return false;
      }
      if (clientId !== null && record.Client_ID !== clientId) {
        return false;
      }
      if (airlineId !== null && record.Airline_ID !== airlineId) {
        return false;
      }
      return true;
    });
  }
  return sortRows(rows);
}

function sortRows(rows) {
  if (!sortColumn) {
    return rows;
  }
  return [...rows].sort((a, b) => {
    const aValue = sortValue(a, sortColumn);
    const bValue = sortValue(b, sortColumn);
    if (aValue < bValue) {
      return sortReverse ? 1 : -1;
    }
    if (aValue > bValue) {
      return sortReverse ? -1 : 1;
    }
    return 0;
  });
}

function sortValue(row, column) {
  if (column === "id") {
    return row.record.ID || row.index;
  }
  if (column === "index") {
    return row.index;
  }
  if (column === "type") {
    return row.record.Type.toLowerCase();
  }
  if (column === "name") {
    return row.record.Name.toLowerCase();
  }
  if (column === "city") {
    return cleanText(row.record.City).toLowerCase();
  }
  if (column === "country") {
    return cleanText(row.record.Country).toLowerCase();
  }
  if (column === "phone") {
    return cleanText(row.record["Phone Number"]).toLowerCase();
  }
  if (column === "company") {
    return cleanText(row.record["Company Name"]).toLowerCase();
  }
  if (column === "client") {
    return namedReference(CLIENT, row.record.Client_ID).toLowerCase();
  }
  if (column === "airline") {
    return namedReference(AIRLINE, row.record.Airline_ID).toLowerCase();
  }
  if (column === "route") {
    return `${row.record["Start City"]} ${row.record["End City"]}`.toLowerCase();
  }
  if (column === "date") {
    return cleanText(row.record.Date).toLowerCase();
  }
  if (column === "summary") {
    return summarizeRecord(row.record).toLowerCase();
  }
  return recordDetails(row.record).toLowerCase();
}

function render() {
  refreshOptionLists();
  const rows = filteredRows();
  drawTableHead();
  elements.body.replaceChildren();

  rows.forEach(({ index, record }) => {
    const tr = document.createElement("tr");
    tr.dataset.index = String(index);
    if (index === selectedIndex) {
      tr.classList.add("selected");
    }
    tableColumns[activeType].forEach(([key]) => {
      const td = document.createElement("td");
      td.textContent = cellValue(record, key);
      tr.append(td);
    });
    tr.addEventListener("click", () => {
      selectedIndex = index;
      render();
      setStatus("Selection made. Use Edit Selected to open the form.");
    });
    elements.body.append(tr);
  });

  elements.status.textContent = `${rows.length} visible records, ${records.length} total records.`;
}

function drawTableHead() {
  elements.head.replaceChildren();
  tableColumns[activeType].forEach(([key, label]) => {
    const th = document.createElement("th");
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = sortColumn === key ? `${label} ${sortReverse ? "down" : "up"}` : label;
    button.addEventListener("click", () => setSort(key));
    th.append(button);
    elements.head.append(th);
  });
}

function cellValue(record, key) {
  if (key === "id") {
    return record.ID;
  }
  if (key === "name") {
    return record.Name;
  }
  if (key === "city") {
    return record.City;
  }
  if (key === "country") {
    return record.Country;
  }
  if (key === "phone") {
    return record["Phone Number"];
  }
  if (key === "company") {
    return record["Company Name"];
  }
  if (key === "client") {
    return namedReference(CLIENT, record.Client_ID);
  }
  if (key === "airline") {
    return namedReference(AIRLINE, record.Airline_ID);
  }
  if (key === "route") {
    return `${record["Start City"]} -> ${record["End City"]}`;
  }
  if (key === "date") {
    return displayDate(record.Date);
  }
  return "";
}

function displayDate(value) {
  const text = cleanText(value).slice(0, 10);
  const match = text.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) {
    return value;
  }
  return `${match[3]}/${match[2]}/${match[1]}`;
}

function setSort(column) {
  if (sortColumn === column) {
    sortReverse = !sortReverse;
  } else {
    sortColumn = column;
    sortReverse = false;
  }
  render();
}

function createRecord(event) {
  event.preventDefault();
  try {
    const record = buildRecord(elements.formType.value, formValues());
    records.push(record);
    saveRecords();
    selectedIndex = records.length - 1;
    setFormValues(record);
    hideFormPanel();
    render();
    setStatus("Record created.");
  } catch (error) {
    setStatus(error.message, true);
  }
}

function updateRecord() {
  if (selectedIndex === null) {
    setStatus("Choose a record to update.", true);
    return;
  }
  try {
    const existing = records[selectedIndex];
    const replacement = buildRecord(existing.Type, formValues(), existing);
    records[selectedIndex] = replacement;
    saveRecords();
    setFormValues(replacement);
    hideFormPanel();
    render();
    setStatus("Record updated.");
  } catch (error) {
    setStatus(error.message, true);
  }
}

function deleteSelectedRecord() {
  if (selectedIndex === null) {
    setStatus("Choose a record to delete.", true);
    return;
  }
  const record = records[selectedIndex];
  const fieldName = record.Type === CLIENT ? "Client_ID" : record.Type === AIRLINE ? "Airline_ID" : null;
  if (fieldName) {
    const isReferenced = records.some((item) => item.Type === FLIGHT && item[fieldName] === record.ID);
    if (isReferenced) {
      setStatus(`Cannot delete ${record.Type.toLowerCase()} record while flights use it.`, true);
      closeDeleteModal();
      return;
    }
  }
  records.splice(selectedIndex, 1);
  selectedIndex = null;
  saveRecords();
  closeDeleteModal();
  clearForm();
  setStatus("Record deleted.");
}

function setStatus(message, isError = false) {
  elements.status.textContent = message;
  elements.status.style.color = isError ? "#c73535" : "";
}

function setActiveType(recordType) {
  activeType = recordType;
  selectedIndex = null;
  sortColumn = null;
  sortReverse = false;
  elements.formType.value = recordType;
  elements.typeFilter.value = "All";
  elements.searchLabel.textContent = `Search ${recordType.toLowerCase()}s`;
  elements.searchText.placeholder =
    recordType === CLIENT
      ? "Search by ID, name, city, country or phone"
      : recordType === AIRLINE
        ? "Search by ID or company name"
        : "Search by client, airline, city or date";
  document.getElementById("new-record").textContent = `Create New ${recordType}`;
  document.getElementById("edit-selected").textContent = "Edit Selected";
  drawForm();
  hideFormPanel();
  render();
}

function openDeleteModal() {
  if (selectedIndex === null) {
    setStatus("Choose a record to delete.", true);
    return;
  }
  elements.deleteModal.classList.add("active");
  elements.deleteModal.setAttribute("aria-hidden", "false");
}

function closeDeleteModal() {
  elements.deleteModal.classList.remove("active");
  elements.deleteModal.setAttribute("aria-hidden", "true");
}

function exportJson() {
  const blob = new Blob([JSON.stringify(records, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "records.json";
  link.click();
  URL.revokeObjectURL(url);
}

function importJson(event) {
  const file = event.target.files[0];
  if (!file) {
    return;
  }
  const reader = new FileReader();
  reader.addEventListener("load", () => {
    try {
      const parsed = JSON.parse(String(reader.result));
      if (!Array.isArray(parsed)) {
        throw new Error("Imported JSON must contain a list of records.");
      }
      validateAllRecords(parsed);
      records = parsed;
      selectedIndex = null;
      saveRecords();
      clearForm();
      render();
      setStatus("JSON records imported.");
    } catch (error) {
      setStatus(error.message, true);
    } finally {
      event.target.value = "";
    }
  });
  reader.readAsText(file);
}

function loadExampleData() {
  records = structuredClone(exampleRecords);
  selectedIndex = null;
  saveRecords();
  clearForm();
  setActiveType(CLIENT);
  setStatus("Example records loaded.");
}

elements.form.addEventListener("submit", createRecord);
elements.updateButton.addEventListener("click", updateRecord);
elements.deleteButton.addEventListener("click", openDeleteModal);
document.getElementById("new-record").addEventListener("click", () => {
  selectedIndex = null;
  elements.form.reset();
  elements.formType.value = activeType;
  drawForm();
  showFormPanel();
  render();
});
document.getElementById("edit-selected").addEventListener("click", () => {
  if (selectedIndex === null) {
    setStatus("Choose a record to edit.", true);
    return;
  }
  setFormValues(records[selectedIndex]);
  showFormPanel();
});
document.getElementById("confirm-delete").addEventListener("click", deleteSelectedRecord);
document.getElementById("cancel-delete").addEventListener("click", closeDeleteModal);
document.getElementById("clear-form").addEventListener("click", clearForm);
document.getElementById("apply-filters").addEventListener("click", render);
document.getElementById("clear-filters").addEventListener("click", () => {
  elements.typeFilter.value = "All";
  elements.searchText.value = "";
  elements.clientFlightFilter.value = "";
  elements.airlineFlightFilter.value = "";
  render();
});
document.getElementById("export-json").addEventListener("click", exportJson);
document.getElementById("load-examples").addEventListener("click", loadExampleData);
elements.importJson.addEventListener("change", importJson);
elements.formType.addEventListener("change", () => {
  activeType = elements.formType.value;
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.tab === activeType);
  });
  drawForm();
  render();
});
elements.typeFilter.addEventListener("change", render);
elements.clientFlightFilter.addEventListener("change", () => {
  const selectedValue = elements.clientFlightFilter.value;
  if (selectedValue) {
    setActiveType(FLIGHT);
    elements.clientFlightFilter.value = selectedValue;
  }
  render();
});
elements.airlineFlightFilter.addEventListener("change", () => {
  const selectedValue = elements.airlineFlightFilter.value;
  if (selectedValue) {
    setActiveType(FLIGHT);
    elements.airlineFlightFilter.value = selectedValue;
  }
  render();
});
elements.searchText.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    render();
  }
});
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
    tab.classList.add("active");
    setActiveType(tab.dataset.tab);
  });
});

setActiveType(CLIENT);
