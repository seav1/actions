name: Mochi Auto Renew

on:
  schedule:
    - cron: '0 */6 * * *'
  workflow_dispatch:

jobs:
  renew:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          repository: seav1/mochi
          token: ${{ secrets.REPO_PAT }}
          ref: main

      - uses: alphaxcv/warp@1.0

      - run: bash run.sh
        env:
          USERNAME: ${{ secrets.MOCHI_USERNAME }}
          PASSWORD: ${{ secrets.MOCHI_PASSWORD }}

      - if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: hidencloud-debug-screenshots
          path: "*.png"
