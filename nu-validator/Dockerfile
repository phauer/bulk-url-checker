FROM java:8u111-jre-alpine
RUN apk --no-cache add curl
RUN curl -o 'vnu.zip' 'https://github.com/validator/validator/releases/download/17.11.1/vnu.jar_17.11.1.zip' --location
RUN mkdir /vnu
RUN unzip vnu.zip -d /vnu
CMD ["java", "-cp", "/vnu/dist/vnu.jar", "nu.validator.servlet.Main", "8888"]