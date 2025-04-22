FROM gcr.io/distroless/java21-debian12

COPY paper.jar app.jar

WORKDIR /app

CMD ["-jar", "../app.jar"]
