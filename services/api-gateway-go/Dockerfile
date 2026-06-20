FROM golang:1.22-alpine AS build

WORKDIR /src
COPY go.mod ./
RUN go mod download
COPY . ./
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/tsi-api-gateway ./cmd/server

FROM alpine:3.20

RUN adduser -D -H -u 10001 appuser
WORKDIR /app
COPY --from=build /out/tsi-api-gateway /app/tsi-api-gateway

ENV TSI_API_ADDR=:8080
EXPOSE 8080

USER appuser
ENTRYPOINT ["/app/tsi-api-gateway"]
