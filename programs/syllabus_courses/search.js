// シラバス検索ページ（output/courses.json を読み込むだけの静的ページ。大学公式サイトには一切アクセスしない）
//
// courses.json の想定スキーマ（scrape.py --by-dept の出力）:
//   { course_name, day_of_week(0-5=月-土), period(1-7), term("spring"|"fall"), room, instructor,
//     departments: [{ faculty, department }, ...] }
// 1つの科目が複数学科の教育課程に含まれる場合（教養科目など）は departments 配列に複数入る。

const DAY_LABELS = ["月", "火", "水", "木", "金", "土"];
const TERM_LABELS = { spring: "前期", fall: "後期" };
const MAX_RESULTS_SHOWN = 500;

const facultySelect = document.getElementById("faculty-select");
const departmentSelect = document.getElementById("department-select");
const queryInput = document.getElementById("query-input");
const resultCountEl = document.getElementById("result-count");
const placeholderHint = document.getElementById("placeholder-hint");
const resultsTable = document.getElementById("results-table");
const resultsBody = document.getElementById("results-body");

let courses = [];

async function boot() {
  const res = await fetch("output/courses.json");
  courses = await res.json();
  populateFacultyOptions();
  render();
}

function populateFacultyOptions() {
  const faculties = new Set();
  for (const c of courses) {
    for (const d of c.departments ?? []) faculties.add(d.faculty);
  }
  for (const f of [...faculties].sort((a, b) => a.localeCompare(b, "ja"))) {
    const opt = document.createElement("option");
    opt.value = f;
    opt.textContent = f;
    facultySelect.appendChild(opt);
  }
}

function populateDepartmentOptions(faculty) {
  departmentSelect.innerHTML = '<option value="">すべての学科</option>';
  departmentSelect.disabled = !faculty;
  if (!faculty) return;

  const depts = new Set();
  for (const c of courses) {
    for (const d of c.departments ?? []) {
      if (d.faculty === faculty) depts.add(d.department);
    }
  }
  for (const d of [...depts].sort((a, b) => a.localeCompare(b, "ja"))) {
    const opt = document.createElement("option");
    opt.value = d;
    opt.textContent = d;
    departmentSelect.appendChild(opt);
  }
}

facultySelect.addEventListener("change", () => {
  populateDepartmentOptions(facultySelect.value);
  render();
});
departmentSelect.addEventListener("change", render);
queryInput.addEventListener("input", render);

function matchesFilters(course, query, faculty, department) {
  if (query && !course.course_name.toLowerCase().includes(query)) return false;
  if (faculty || department) {
    const depts = course.departments ?? [];
    const hasMatch = depts.some((d) => {
      if (faculty && d.faculty !== faculty) return false;
      if (department && d.department !== department) return false;
      return true;
    });
    if (!hasMatch) return false;
  }
  return true;
}

function scheduleLabel(course) {
  return `${DAY_LABELS[course.day_of_week]}曜 ${course.period}限`;
}

function departmentsLabel(course) {
  return (course.departments ?? [])
    .map((d) => `${d.faculty}/${d.department}`)
    .join(", ");
}

function render() {
  const query = queryInput.value.trim().toLowerCase();
  const faculty = facultySelect.value;
  const department = departmentSelect.value;

  const active = Boolean(query || faculty);
  placeholderHint.hidden = active;
  resultsTable.hidden = !active;
  if (!active) {
    resultCountEl.textContent = "";
    return;
  }

  const matched = courses.filter((c) => matchesFilters(c, query, faculty, department));
  const shown = matched.slice(0, MAX_RESULTS_SHOWN);

  resultCountEl.textContent = matched.length > MAX_RESULTS_SHOWN
    ? `${matched.length}件中 ${MAX_RESULTS_SHOWN}件を表示（絞り込んでください）`
    : `${matched.length}件`;

  resultsBody.replaceChildren();
  for (const c of shown) {
    const tr = document.createElement("tr");
    const cells = [
      c.course_name,
      TERM_LABELS[c.term] ?? c.term,
      scheduleLabel(c),
      c.instructor ?? "",
      departmentsLabel(c),
    ];
    for (const text of cells) {
      const td = document.createElement("td");
      td.textContent = text;
      tr.appendChild(td);
    }
    resultsBody.appendChild(tr);
  }
}

void boot();
