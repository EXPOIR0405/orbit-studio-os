import { test, expect } from "@playwright/test";
test("mock mission, routing, approval and audit without live calls", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "새 미션", exact: true }).click();
  await page.getByLabel("미션 이름").fill("UI 검증 미션");
  // <option>은 toBeDisabled()가 disabled 속성을 인식하지 못해 속성으로 확인
  await expect(
    page.getByRole("option", { name: "OpenAI · 비활성화됨" }),
  ).toHaveAttribute("disabled", "");
  await page.getByLabel("작업 범위").selectOption("story");
  await page.getByRole("button", { name: "미션 만들기", exact: true }).click();
  await expect(
    page.getByText("운영자가 작업 범위를 직접 선택했습니다.", { exact: false }),
  ).toBeVisible();
  await page.getByRole("button", { name: "계획 확인 · 실행" }).click();
  await expect(
    page.getByRole("button", { name: "패키지 승인", exact: true }),
  ).toBeEnabled({ timeout: 20000 });
  await page.getByRole("button", { name: "패키지 승인", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "승인 패키지 내보내기" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Audit", exact: true }).click();
  await expect(page.getByText("실제 저장된 이벤트")).toBeVisible();
  await expect(
    page.getByText("search_sources · ok", { exact: false }).first(),
  ).toBeVisible();
});
