(() => {
  "use strict";
  const chapter = document.getElementById("return");
  if (!chapter) return;
  chapter.querySelector("#saveReturn").addEventListener("click", () => {
    const lines = ["青甘银川 · 归来", ""];
    chapter.querySelectorAll(".return-entry").forEach((entry) => {
      lines.push(...[...entry.querySelectorAll("p")].map((paragraph) => paragraph.textContent.trim()), "");
    });
    const url = URL.createObjectURL(new Blob([lines.join("\n\n")], { type: "text/plain;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "2026青甘银川-归来.txt";
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 30000);
    chapter.querySelector("#returnSaveStatus").textContent = "已生成文字文件。";
  });
})();
