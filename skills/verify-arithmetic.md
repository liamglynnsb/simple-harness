name: verify-arithmetic
description: Use whenever the user asks you to calculate, add, subtract, multiply, divide or work out any number, including totals, splitting an amount, or percentages. It verifies each result by solving the inverse equation.
---
When you return the results of an arithmetic calculation, return the inverse on a new line with the label "Inverse:". Work out both with the calculator tool, never in your head.

1. Find the inverse by starting from the result:
   - for a + b: subtract b from the result. You should get a.
   - for a - b: add b to the result. You should get a.
   - for a * b: divide the result by b. You should get a.
   - for a / b: multiply the result by b. You should get a.
2. If you get a back, the result is verified. For a division that does not end (such
   as 10 / 3), a difference in the last few decimal places still counts as verified.
3. If you do not get a back, do not give the result. Say "mismatch" and report the
   result and what the inverse gave you.
4. Zeros: if a multiplication has a factor of 0, divide the result by the other factor
   instead. If both factors are 0, write "(not verifiable)" instead of "(verified)". If
   you are asked to divide by 0, the calculator will return an error: report it and do
   not verify.
5. If the question needs several calculations in a row, verify each one separately.
6. Give the answer in exactly this form, on two lines:
   expression = result (verified)
   Inverse: inverse expression = a
   Example:
   12 * 12 = 144 (verified)
   Inverse: 144 / 12 = 12

Do this for every calculation, even a simple one.
